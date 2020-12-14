#!/usr/bin/env python3
# Copyright (c) 2013 Qumulo, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

# qumulo_python_versions = { 3 }

"""
This script sends out three types of configurable alerts based on matching
criteria as defined in the accompanying configuration file. The alerts that can
be configured are:
    - Quota Capacity Exceeded (Soft Quota Alert)
    - Cluster Capacity Exceeded
    - Replication Relationship Errors

The alerts will be sent if they are new, and will not re-alert on the same
condition if the script is run again. However, if the rule being checked exceeds
a new threshold, it will alert on the new higher threshold.
"""

# Import Python Libraries
import argparse
import datetime
import json
import logging
import os
import smtplib
import sys
from collections import namedtuple
from email.mime.text import MIMEText
from typing import Any, Dict, List, Sequence, Tuple

# Import Qumulo REST Libraries
import qumulo.lib.auth
import qumulo.lib.opts
import qumulo.lib.request
import qumulo.rest

#   ____ _     ___  ____    _    _     ____
#  / ___| |   / _ \| __ )  / \  | |   / ___|
# | |  _| |  | | | |  _ \ / _ \ | |   \___ \
# | |_| | |__| |_| | |_) / ___ \| |___ ___) |
#  \____|_____\___/|____/_/   \_\_____|____/

log = logging.getLogger(__name__)

KILOBYTE = 1000
MEGABYTE = 1000 * KILOBYTE
GIGABYTE = 1000 * MEGABYTE
TERABYTE = 1000 * GIGABYTE

EmailSettings = namedtuple(
    'EmailSettings', ['sender', 'server', 'cluster_name', 'no_emails']
)

RestInfo = namedtuple('RestInfo', ['conninfo', 'creds'])


#  _   _ _____ _     ____  _____ ____  ____
# | | | | ____| |   |  _ \| ____|  _ \/ ___|
# | |_| |  _| | |   | |_) |  _| | |_) \___ \
# |  _  | |___| |___|  __/| |___|  _ < ___) |
# |_| |_|_____|_____|_|   |_____|_| \_\____/


def load_json(file: str) -> Dict[str, Any]:
    """Load a file and ensure that it's valid JSON."""
    try:
        file_fh = open(file, 'r')
        data = json.load(file_fh)
        return data
    except ValueError as error:
        sys.exit(f'Invalid JSON file: {file}. Error: {error}')
    finally:
        file_fh.close()


def humanize_bytes(num: float, suffix: str = 'B') -> str:
    """
    Convert bytes to a more human friendly size in base 10 to match the WebUI.
    """
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1000.0:
            return '%3.1f%s%s' % (num, unit, suffix)
        num /= 1000.0
    return '%.1f%s%s' % (num, 'Y', suffix)


def cluster_login(username: str, password: str, cluster: str, port: int) -> RestInfo:
    """Generate the credentials object used to query Qumulo's API."""
    # Open a connection to the REST server on the cluster.
    conninfo = qumulo.lib.request.Connection(cluster, int(port))

    # Get the bearer token by passing through 'conninfo'.
    results, _etag = qumulo.rest.auth.login(conninfo, None, username, password)

    # Create a credentials object to use in the REST calls.
    creds = qumulo.lib.auth.Credentials.from_login_response(results)

    return RestInfo(conninfo, creds)


def load_config(config_file: str) -> Dict[str, Any]:
    if os.path.exists(config_file):
        return load_json(config_file)
    else:
        sys.exit(f'Configuration file "{config_file}" does not exist.')


def load_history(history_file: str) -> Dict[str, Any]:
    """Load the history file, if available. Otherwise return a blank config."""
    if os.path.exists(history_file):
        return load_json(history_file)
    else:
        log.debug(f'History file "{history_file}" does not exist.')
        return {'quotas': {}, 'capacity': {}, 'replication': {}}


def save_history(history_file: str, history: Dict[str, Any]) -> None:
    """Save the updated history file, if available."""

    log.debug(f'Updating history file: {history_file}')
    history_json = json.dumps(history)

    with open(history_file, 'w') as f:
        f.write(history_json)
        f.close()


def get_email_settings(config: Dict[str, Any], no_emails: bool) -> EmailSettings:
    return EmailSettings(
        config['email_settings']['sender_address'],
        config['email_settings']['server_address'],
        config['cluster_settings']['cluster_name'],
        no_emails,
    )


def get_rest_credentials(config: Dict[str, Any]) -> RestInfo:
    return cluster_login(
        config['cluster_settings']['username'],
        config['cluster_settings']['password'],
        config['cluster_settings']['cluster_address'],
        config['cluster_settings']['rest_port'],
    )


def send_or_log_mail(
    no_emails: bool,
    server: str,
    sender: str,
    recipients: List[str],
    subject: str,
    body: str,
) -> None:
    """
    Send or log an email with the message generated by other functions.
    """
    # Add a timestamp to the body.
    body += '<br><br>Alert sent on {}'.format(
        datetime.datetime.now().strftime('%A, %d. %B %Y %I:%M%p')
    )

    # Compose the email to be sent based off received data.
    mmsg = MIMEText(body, 'html')
    mmsg['Subject'] = subject
    mmsg['From'] = sender
    mmsg['To'] = ', '.join(recipients)

    # Send the email to the server as the sender_address.
    if no_emails:
        log.info('Skipping sending this email: \n\n{}\n\n'.format(mmsg.as_string()))
    else:
        session = smtplib.SMTP(server)
        session.sendmail(sender, recipients, mmsg.as_string())
        session.quit()


#   ___  _   _  ___ _____  _    ____
#  / _ \| | | |/ _ \_   _|/ \  / ___|
# | | | | | | | | | || | / _ \ \___ \
# | |_| | |_| | |_| || |/ ___ \ ___) |
#  \__\_\\___/ \___/ |_/_/   \_\____/


def quota_capacity_check(
    email_settings: EmailSettings,
    rest_info: RestInfo,
    config: Dict[str, Any],
    options: argparse.Namespace,
) -> None:
    """
    Check if any quotas have exeeded their defined thresholds. If so, trigger
    an alert check, which can email, log, or do nothing depeding on the
    rules. If no rule is configured, the default rule will apply to undefined
    quotas.
    """
    history = load_history(options.history_file)
    log.info(f'Checking the quotas on {rest_info.conninfo.host}')

    total_cap, _used_cap, _used_cap_pct = cluster_get_fs_usage(rest_info)
    quotas = get_current_quotas(rest_info)

    # Process config and apply rules to quotas if defined, else apply default rules.
    processed_quotas = process_quotas_and_rules(quotas, config)

    # Check which quotas are currently exceeding a rule's alert threshold.
    alert_quotas = get_alerting_quotas(processed_quotas)

    # For each alerting quota rule, compare with the history and determine if
    # a log or email is necessary. Remove any quotas no longer alerting.
    notify_quotas, history = process_quotas_with_history(alert_quotas, history)

    for quota_path, rules in notify_quotas.items():
        for rule_name, rule_details in rules.items():
            log.info(
                f'Quota "{quota_path}" exceeds threshold of '
                f'{rule_details["alert_threshold"]} for rule: "{rule_name}"'
            )
            quota_send_alert(
                email_settings, quota_path, rule_details, humanize_bytes(total_cap),
            )

    save_history(options.history_file, history)


def get_current_quotas(rest_info: RestInfo) -> Dict[str, Any]:
    """Get the status of all the quotas on the cluster."""
    quotas = {}

    responses = qumulo.rest.quota.get_all_quotas_with_status(
        rest_info.conninfo, rest_info.creds
    )

    # Convert the PagingIterator into a dict with the quota path as key.
    quotas = {
        quota['path']: quota
        for response in responses
        for quota in response.data['quotas']
    }

    return quotas


def process_quotas_and_rules(
    quotas: Dict[str, Any], config: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Take a list of quotas and the configuration, sort the quotas by configured and
    unconfigured. Apply the default configuration to quotas not defined in the config
    file. Return a combined list of all paths with their respective capacities and
    rules.
    """
    defined_rules = config['quota_rules']
    undefined_rules = config['default_quota_rules']

    defined_quotas = {}
    undefined_quotas = {}

    for quota in quotas:
        if quota in defined_rules:
            defined_quotas[quota] = {**quotas[quota], **defined_rules[quota]}
        elif quota not in defined_rules:
            undefined_quotas[quota] = {**quotas[quota], **undefined_rules}

    processed_quotas = {**defined_quotas, **undefined_quotas}

    return processed_quotas


def get_alerting_quotas(quotas: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Compare all quota's current used capacity against each rule. Return the quotas
    with the rules that would be in an alert state.
    """

    alert_quotas = {}

    for path, quota in quotas.items():
        quota_used = humanize_bytes(int(quota['capacity_usage']))
        quota_limit = humanize_bytes(int(quota['limit']))
        pct_used = round(
            (float(quota['capacity_usage']) / float(quota['limit'])) * 100, 2
        )

        alert_rules = {}
        for r_name, rule in quota['rules'].items():

            log.debug(f'Checking quota rule "{r_name}" on path "{path}".')

            # Find highest exceeded threshold per rule.
            alert_threshold = 0

            for threshold in rule['thresholds']:
                if threshold == 0:
                    log.warning(f'Quota rule {r_name} has a threshold of 0.')
                if pct_used > threshold:
                    alert_threshold = threshold

            if alert_threshold > 0:
                log.info(
                    f'Quota "{path}" usage of {pct_used}% exceeds '
                    f'configured threshold of {alert_threshold}%.'
                )
                alert_rules[r_name] = {
                    **rule,
                    'alert_threshold': alert_threshold,
                    'pct_used': pct_used,
                    'quota_used': quota_used,
                    'quota_limit': quota_limit,
                }

        if alert_rules:
            alert_quotas[path] = alert_rules

    return alert_quotas


def process_quotas_with_history(
    alert_quotas: Dict[str, Dict[str, Any]], history: Dict[str, Any]
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Compare alerting quota rules with the quota rules in the history and update
    the history if needed."""

    notify_quotas = {}

    # Check the history for any quotas we have previously alerted on.
    for alert_quota, alert_rules in alert_quotas.items():

        # Assume new quota, alert for all rules.
        if alert_quota not in history['quotas']:
            notify_quotas[alert_quota] = alert_rules
            history['quotas'][alert_quota] = alert_rules
            continue

        # Existing quota, check all rules.
        if alert_quota in history['quotas']:
            if alert_quota not in notify_quotas:
                notify_quotas[alert_quota] = {}
            for rule_name, rule_info in alert_rules.items():

                # Existing quota, new rule; alert.
                if rule_name not in history['quotas'][alert_quota]:

                    # Edge case where a rule could be removed and a second rule
                    # added in between. Need to ensure that the alert_path exists
                    # as a key.
                    if alert_quota not in notify_quotas:
                        notify_quotas[alert_quota] = {}

                    notify_quotas[alert_quota][rule_name] = rule_info
                    history['quotas'][alert_quota][rule_name] = rule_info
                    continue

                # Existing quota, new threshold exceeded; alert.
                if rule_name in history['quotas'][alert_quota]:
                    if (
                        rule_info['alert_threshold']
                        > history['quotas'][alert_quota][rule_name]['alert_threshold']
                    ):
                        notify_quotas[alert_quota][rule_name] = rule_info
                        history['quotas'][alert_quota][rule_name] = rule_info
                    else:
                        history['quotas'][alert_quota][rule_name] = rule_info

    # Clean up history for any quotas or rules no longer alerting.
    quotas_to_remove = []
    rules_to_remove = []

    for expired_quota in history['quotas']:
        if expired_quota not in alert_quotas:
            quotas_to_remove.append(expired_quota)
            continue
        for expired_rule in history['quotas'][expired_quota]:
            if expired_rule not in alert_quotas[expired_quota]:
                rules_to_remove.append([expired_quota, expired_rule])

    try:
        for q in quotas_to_remove:
            del history['quotas'][q]
    except KeyError:
        log.warning(f'Unable to remove quota on path {q} from the history.')

    try:
        for r in rules_to_remove:
            del history['quotas'][r[0]][r[1]]
    except KeyError:
        log.warning(
            f'Unable to remove quota rule {r[1]} on path {r[0]} from the history.'
        )

    return notify_quotas, history


def quota_send_alert(
    email_settings: EmailSettings,
    quota_path: str,
    rule_details: Dict[str, Any],
    total_cap: str,
) -> None:
    """Generate the Subject and Body for the soft quota alert."""

    subject = f'{email_settings.cluster_name}: Soft quota alert on path {quota_path}'

    body = f'The quota on directory path "{quota_path}" has exceeded the usage threshold of {rule_details["alert_threshold"]}%.<br><br>Current quota usage is {rule_details["quota_used"]} out of {rule_details["quota_limit"]}.  ({rule_details["pct_used"]}% full)'

    if rule_details['include_capacity']:
        body += f'<br><br>Cluster total capacity: {total_cap}'

    if rule_details['custom_msg']:
        body += f'<br><br>{rule_details["custom_msg"]}'

    send_or_log_mail(
        email_settings.no_emails,
        email_settings.server,
        email_settings.sender,
        rule_details['mail_to'],
        subject,
        body,
    )


#   ____    _    ____   _    ____ ___ _______   __
#  / ___|  / \  |  _ \ / \  / ___|_ _|_   _\ \ / /
# | |     / _ \ | |_) / _ \| |    | |  | |  \ V /
# | |___ / ___ \|  __/ ___ \ |___ | |  | |   | |
#  \____/_/   \_\_| /_/   \_\____|___| |_|   |_|


def cluster_capacity_check(
    email_settings: EmailSettings,
    rest_info: RestInfo,
    config: Dict[str, Any],
    options: argparse.Namespace,
) -> None:
    """
    Check if the capacity of the cluster has exceeded a threshold. If so,
    trigger an email alert if we have not done so already.
    """
    log.info(f'Checking the cluster capacity for {rest_info.conninfo.host}')
    history = load_history(options.history_file)

    total, used, used_pct = cluster_get_fs_usage(rest_info)

    send_alert = False
    for rule_name, rule_info in config['capacity_rules'].items():
        send_alert, exceeded_threshold = cluster_capacity_process_rule(
            rule_name, rule_info, used_pct, history, options
        )

        if send_alert:
            cluster_capacity_send_alert(
                rule_info, email_settings, total, used, used_pct, exceeded_threshold
            )


def cluster_get_fs_usage(rest_info: RestInfo) -> Tuple[int, int, float]:
    fs_stats = qumulo.rest.fs.read_fs_stats(rest_info.conninfo, rest_info.creds)
    total_capacity = int(fs_stats[0]['total_size_bytes'])
    used_capacity = int(fs_stats[0]['total_size_bytes']) - int(
        fs_stats[0]['free_size_bytes']
    )
    used_capacity_pct = round((float(used_capacity) / float(total_capacity)) * 100, 2)

    return total_capacity, used_capacity, used_capacity_pct


def cluster_capacity_process_rule(
    rule_name: str,
    rule_info: Dict[str, Any],
    used_pct: float,
    history: Dict[str, Any],
    options: argparse.Namespace,
) -> Tuple[bool, int]:
    """Find highest exceeded threshold and alert if needed. Save to history if
    new or next threshold exceeded. Remove from history if thresholds not
    exceeded."""
    send_alert = False
    exceeded_threshold = None

    for threshold in rule_info['thresholds']:
        if used_pct > threshold:
            exceeded_threshold = threshold

    # Determine if an alert is needed.
    if exceeded_threshold:
        if rule_name in history['capacity']:
            if exceeded_threshold > history['capacity'][rule_name]['alert_threshold']:
                history['capacity'][rule_name] = {'alert_threshold': exceeded_threshold}
                send_alert = True
        else:
            history['capacity'][rule_name] = {'alert_threshold': exceeded_threshold}
            send_alert = True

    # Clean up the history as needed.
    if not exceeded_threshold:
        if rule_name in history['capacity']:
            try:
                del history['capacity'][rule_name]
            except KeyError:
                log.error(f'Unable to remove capacity rule {rule_name}.')

    if send_alert:
        log.info(f'Cluster usage of {used_pct} exceeds threshold {exceeded_threshold}.')

    save_history(options.history_file, history)

    return send_alert, exceeded_threshold


def cluster_capacity_send_alert(
    rule: Dict[str, Any],
    email_settings: EmailSettings,
    total: int,
    used: int,
    used_pct: float,
    threshold: int,
) -> None:
    """Craft and send a cluster capacity alert due to an exceeded threshold."""
    human_total = humanize_bytes(int(total))
    human_used = humanize_bytes(int(used))

    subject = f'{email_settings.cluster_name}: Cluster capacity alert. Usage has exceeded {threshold}'

    body = (
        f'The cluster "{email_settings.cluster_name}" has exceeded its usage'
        f'threshold of {threshold}%. Current usage is {human_used} out of '
        f'{human_total} ({used_pct}% full).'
    )

    if rule['custom_msg']:
        body += '\n{}'.format(rule['custom_msg'])

    body = body.replace('\n', '<br><br>')

    send_or_log_mail(
        email_settings.no_emails,
        email_settings.server,
        email_settings.sender,
        rule['mail_to'],
        subject,
        body,
    )


#  ____  _____ ____  _     ___ ____    _  _____ ___ ___  _   _
# |  _ \| ____|  _ \| |   |_ _/ ___|  / \|_   _|_ _/ _ \| \ | |
# | |_) |  _| | |_) | |    | | |     / _ \ | |  | | | | |  \| |
# |  _ <| |___|  __/| |___ | | |___ / ___ \| |  | | |_| | |\  |
# |_| \_\_____|_|   |_____|___\____/_/   \_\_| |___\___/|_| \_|


def replication_status_check(
    email_settings: EmailSettings,
    rest_info: RestInfo,
    config: Dict[str, Any],
    options: argparse.Namespace,
) -> None:
    """
    Check all source & target replication relationships for errors. Trigger an
    alert if any show errors.
    """
    log.info('Checking replication relationships')

    history = load_history(options.history_file)

    err_relationships = None
    qr = qumulo.rest

    src_relationships = qr.replication.list_source_relationship_statuses(
        rest_info.conninfo, rest_info.creds
    )[0]
    err_relationships = [r for r in src_relationships if r['error_from_last_job']]

    tgt_relationships = qr.replication.list_target_relationship_statuses(
        rest_info.conninfo, rest_info.creds
    )[0]
    err_relationships += [r for r in tgt_relationships if r['error_from_last_job']]

    for rule_name, rule_info in config['replication_rules'].items():
        send_alert = False
        send_alert = replication_process_rules(
            rule_name, rule_info, err_relationships, history, options
        )
        if send_alert:
            log.info('Errors found in replication relationships')
            replication_send_alert(email_settings, rule_info, err_relationships)


def replication_process_rules(
    rule_name: str,
    rule_info: Dict[str, Any],
    err_relationships: List[str],
    history: Dict[str, Any],
    options: argparse.Namespace,
) -> bool:
    send_alert = False

    # Determine if an alert is needed for all relationships, if an alert already
    # exists, do nothing.
    if err_relationships:
        if rule_name not in history['replication']:
            history['replication'][rule_name] = rule_info
            send_alert = True

    # Clear out old alerts if there are no erroring relationships.
    else:
        if rule_name in history['replication']:
            del history['replication'][rule_name]

    if send_alert:
        log.info(
            f'Sending replication relationship error alert {rule_name} for {err_relationships}'
        )

    save_history(options.history_file, history)

    return send_alert


def replication_send_alert(
    email_settings: EmailSettings, rule_info: Dict[str, Any], err_relationships: Any,
) -> None:
    """ Send an alert because a relationship has an error.
    """
    subject = f'{email_settings.cluster_name}: Relationship error alert.'
    newline = '<br><br>'

    body = ''
    body += 'The following replication relationships have reported an error:'
    body += newline
    for r in err_relationships:
        tmp_body = """Source cluster name: {0[source_cluster_name]}
Source replication root path: {0[source_root_path]}
Target cluster name: {0[target_cluster_name]}
Target replication root path: {0[target_root_path]}
Recovery point: {0[recovery_point]}
Error from last replication job: {0[error_from_last_job]}\n""".format(
            r
        )

        tmp_body = tmp_body.replace('\n', newline)
        body += tmp_body

    msg_body = body + rule_info['custom_msg']
    send_or_log_mail(
        email_settings.no_emails,
        email_settings.server,
        email_settings.sender,
        rule_info['mail_to'],
        subject,
        msg_body,
    )


#  __  __    _    ___ _   _
# |  \/  |  / \  |_ _| \ | |
# | |\/| | / _ \  | ||  \| |
# | |  | |/ ___ \ | || |\  |
# |_|  |_/_/   \_\___|_| \_|


def setup_logging(debug: bool) -> None:
    if debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        stream=sys.stdout, level=level, format='%(asctime)s %(levelname)s: %(message)s',
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='This script will generate email alerts when run based \
                    on the configuration passed through in --config. This \
                    script requires the Qumulo API Tools which can be \
                    downloaded using pip or from the cluster itself.'
    )

    parser.add_argument(
        '-c',
        '--config',
        dest='config_file',
        required=True,
        help='Configuration file to be used.',
    )

    parser.add_argument(
        '-H',
        '--history',
        dest='history_file',
        required=False,
        default='history.json',
        help='File used to store the alert history.',
    )

    parser.add_argument(
        '--no-emails',
        action='store_true',
        help='Do not send emails; log them to stdout instead.',
    )

    parser.add_argument(
        '--debug',
        required=False,
        default=False,
        action='store_true',
        help='Enable debug logging for the script.',
    )

    return parser.parse_args(argv)


def main(options: argparse.Namespace) -> int:

    setup_logging(options.debug)

    config = load_config(options.config_file)
    email_settings = get_email_settings(config, options.no_emails)
    rest_creds = get_rest_credentials(config)

    cluster_checks = [
        cluster_capacity_check,
        quota_capacity_check,
        replication_status_check,
    ]

    for cluster_check in cluster_checks:
        cluster_check(email_settings, rest_creds, config, options)

    return 0


if __name__ == '__main__':
    sys.exit(main(parse_args(sys.argv[1:])))
