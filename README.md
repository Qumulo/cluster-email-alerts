# Cluster Alerts for Qumulo

## Table of contents

  * [Updates](#updates)
  * [Introduction](#introduction)
  * [Installation](#installation)
  * [Configuration](#configuration)
  * [Examples](#examples)
  * [Notes](#notes)

## Updates

  * July 25, 2023
    * Removed deprecation notice. Please see Support Statement (below) on limitations regarding SLA for this software.
      
  * December 10, 2020
    * The configuration file JSON schema changed to enable new functionality.
    * The script now supports a default rule that applies to all quotas. There is no need to define a rule for every quota.
    * Multiple rules can now be specified per each of the checks, including default quota rules.
    * Script now stores the alert history in a file to prevent alerting multiple times for the same condition.
    * Script was updated to only alert if an condition is new or crosses a higher alerting threshold.

## Introduction
This script generates email alerts for a Qumulo cluster using the REST API. 

The Qumulo API tools are required to make the script work and and they are available for download from your Qumulo cluster. For more information, please check out the [Qumulo GitHub](https://qumulo.github.io/) page for more information on the API. T

he script is aimed to be customized to the user's desire using 'alert rules' or a list of several JSON schemas; each with its own configuration. Currently, the script generates three different types of alerts:

  * Cluster Capacity by Threshold
  * Directory Quotas by Threshold
  * Replication Relationships by Error (Both Source & Target)

If any of the alert conditions are triggered, a single email will be sent to all of the configured recipients. Any alert can also include a custom message by filling in the `custom_msg` field for each 'rule'. A summary of the expected behavior of this script is:

  * The alert conditions are checked a single time when the script is run.
  * Any rules or alerts that are triggered are stored in a local file `history.json`.
  * If the current alert condition matches an entry in the `history.json` file, then nothing is done.
  * If the current alert condition matches and exceeds what is in the `history.json` file, then a new alert is sent.
  * If the current rule condition does not match any alert, it is removed from the `history.json` file.

The suggested method to run this script is via a `cron` job which periodically executes the script. For more information regarding `cron` please check out [Ubuntu's Cron How To](https://help.ubuntu.com/community/CronHowto).

Lastly, all email alerts include a time stamp indicating when the alert was sent.

## Installation
The script has the following requirements:

  * A Linux machine, preferably Ubuntu 16.04 or newer.
  * Python 3.6 or newer. NOTE: Python2 is not supported.
  * Qumulo API SDK 3.1.1 or newer installed for Python3. (aka. API Tools)
  * An SMTP server running on port TCP 25. (TLS not available.)

To install and use this script:

  1. Use `pip` to install the Qumulo Python API tools: `pip3 install qumulo-api`.
  2. Clone this repository using `git` or download the `cluster_email_alerts.py`.
  If you have questions cloning a repo, please see GitHub's
  [Cloning a repository](https://help.github.com/en/articles/cloning-a-repository).
  3. Use `example_config.json` as a guide to creating a `config.json` with your alerting rules.
  4. Invoke the script by running `python ./cluster_email_alerts.py --config config.json` from the cloned directory.

## Alert Rule Configuration
At this point, it is expected that you have a Qumulo cluster with the API Tools installed and the `cluster_email_alerts.py` script downloaded. If this is done, you can create a `config.json` configuration file to suit your needs. The general steps are:

  1. Use `example_config.json` as a guide to creating a `config.json` with your alerting rules. The fields for this file are described after this section.
  2. Set up a `cron` job to run as often as you like to check for alerts. See [CronHowto](https://help.ubuntu.com/community/CronHowto) if you have any questions. Example command `./cluster_email_alerts.py --config /root/config.json`

The `config.json` file contains 6 stanzas and each can have multiple objects. These stanzas are groups objects of `rules` and are individually interpreted by the script. The stanzas are:

  1. Email Settings
     - `server_address` - The email server or relay that will route the emails sent by the script.
     - `sender_address` - The email address (fake or real) that the alerts should have in the 'From:' field. A suggestion is to use the cluster's name.

  2. Cluster Settings
     - `cluster_name` - A friendly name for the cluster to generate alerts for.
     - `cluster_address` - FQDN or IP address of the cluster.
     - `username` - The username to access the REST API.
     - `password` - The password to access the REST API.
     - `rest_port` - The TCP port on which to access the REST API. Default of 8000.

  3. Quota Rules - These rule triggers when a directory quota exceeds a used percentage threshold. The fields are:
     - `quota_rules` - The top level stanza containing all DEFINED quota rules.
       - `path` - The path on which a directory quota exists. This path will be looked up using the API to get the current usage.
         - `rules` - The collection of rules for this particular path.
           - `$RULE_NAME` - The friendly name of the rule. There can be multiple of these stanzas; one for each rule for this specific path.
             - `thresholds` - A list of integers that describe the thresholds at which to send an alert. If exceeded, the script will only send the highest exceeded threshold for each rule.
             - `mail_to` - A list of email addresses to send an alert to; only for this specific rule.
             - `include_capacity` - A boolean that allows you to include or exclude including the current total capacity of the cluster.
             - `custom_msg` - A field that will be included with each quota rule to provide instructions or guidance to the email recipients. If blank, it will not be included.

  4. Default Quota Rules - These rules trigger for all directory quotas that do NOT have a defined rule, in the `quota_rules` stanza.
     - `default_quota_rules` - The top level stanza containing all NON-DEFINED quota rules.
       - `rules` - The collection of rules for the default or non-defined quotas.
         - `$RULE_NAME` - The friendly name of the rule. There can be multiple of these stanzas; one per rule.
           - `thresholds` - A list of integers that describe the thresholds at which to send an alert. If exceeded, the script will only send the highest exceeded threshold for each rule.
           - `mail_to` - A list of email addresses to send an alert to; only for this specific rule.
           - `include_capacity` - A boolean that allows you to include or exclude including the current total capacity of the cluster.
           - `custom_msg` - A field that will be included with each quota rule to provide instructions or guidance to the email recipients. If blank, it will not be included.

  4. Capacity Rules - This rule will trigger if the cluster exceeds a certain used percentage threshold. The fields are:
     - `thresholds` - Same as the quota, what thresholds to alert on. Only the highest matching threshold will be alerted on.
     - `mail_to` - Who to send the alert to.
     - `custom_msg` - A field that will be included with each rule to provide instructions or guidance to the email recipients. If blank, it will not be included.

  5. Replication Rules - This rule will trigger if any replication relationship has an error; source or target. The fields are:
     - `mail_to` - Who to send the alert to.
     - `custom_msg` - A field that will be included with each rule to provide instructions or guidance to the email recipients. If blank, it will not be included.

## Permissions
This script needs cluster and file system permissions to run. The user provided
to this script through the config file must be granted the following Qumulo
privileges:
```
PRIVILEGE_FS_ATTRIBUTES_READ
PRIVILEGE_QUOTA_READ
PRIVILEGE_REPLICATION_SOURCE_READ
PRIVILEGE_REPLICATION_TARGET_READ
```

The `Observers` role is configured with these (and other) privileges by default.

* On clusters running Qumulo Core 4.1.3 and older, the user must also be granted file system permission to traverse to and to read the directories configured with alerts. For example, for an alert on path `/foo/bar/`, the user must have Traverse permission on `/` and `foo/`, and Read permission on `bar/`. Alternatively to configuring file system permissions, the user can be granted the Qumulo role `PRIVILEGE_FILE_FULL_ACCESS`. This privilege confers full read and write access to the user regardless of file system permissions.
* On clusters running Qumulo Core 4.1.4 and newer, no explicit file systerm permission is needed to make the script work.

## FAQ

  1. What if I want multiple emails to be sent for the same quota?
     - Add multiple quota rules. Each one will be triggered individually.
  2. Will multiple emails be sent if a quota exceeds them?
     - No, a single email will be sent for the highest exceeded threshold.
  3. Will the same alert be sent if the quota has already exceeded a threshold?
     - No, the alert state will be remembered in the `history.json` file. A new alert will only be sent if the next threshold is exceeded or if the alert condition is cleared and it re-alerts.
  4. How do I send different `custom_msg` depending on the threshold?
     - Create multiple rules, with a different `custom_msg` each. Note that this can result in sending two emails, one for each rule.

## Examples
An example configuration is uploaded to this GitHub for ease of use, `example_config.json`. Use this as a template to build your own rule set. The email alerts will be similar to these:

### Quota Alert

```
The quota 'Engineering - Certification on directory path /cert_tests/ has exceeded it's usage threshold of 95.0%.

Current usage is 961.2MB out of 1.0GB. (96.2% full)

Cluster total capacity: 48.0TB

Certification is filling up the cluster, please clear out some space. If you would ike more space, please reach out to IT at 1-800-IT-DEPARTMENT

Alert sent on Thursday, 18. July 2019 04:10PM
```



### Capacity Alert
```
The cluster 'Music' has exceeded its usage threshold of 75.0%.

Current usage is 37.6TB out of 48.0TB (78.43% full).

Alert sent on Thursday, 18. July 2019 04:08PM
```


### Replication Rules
```
The following replication relationships have reported an error:

Source cluster name: TestCluster-SRC

Source replication root path: /users

Target cluster name: TestCluster-TGT

Target replication root path: /bkup/users

Recovery point: 2019-07-17T23:17:48.49836359Z

Error from last replication job: /users/john_doe/devvm_backup/qinstall_custom.qimg cannot be replicated because it belongs to local user ben. Either remove all local users and groups from the file or edit this relationship to enable mapping local IDs to NFS IDs.

Replication has an issue, please contact 1-800-IT-DEPARTMENT.

Alert sent on Thursday, 18. July 2019 01:57AM
```


## Notes
The script has some limitations or caveats; they are:
  * Email server or relay must speak SMTP over port TCP 25.
  * Script must be run to alert; the recommended method is a `cron` job that runs as often as desired.
  * It will send one email alert per JSON object in the configuration file.
  * If multiple alerts for the same path are required, multiple JSON objects should be present.
  * If you would like to test this on a local email server, please see [Test Email Server](#test-email-server)
  * To test this script without sending emails, use the flag `--no-emails` when invoking the script.


## Test Email Server
If you do not already have an email server to use, you can create a local one using Ubuntu and some free open source utilities. To set up a test email server on a fresh install of Ubuntu 18.04:

1. Edit `/etc/hosts` file and add in your test domain name. In this case we'll be using "@localhost.com" email addresses. Therefore, what you need to add to the `/etc/hosts` file would be:
```
127.0.0.1    localhost.com
```

2. Install the actual email server `postfix` with `sudo apt-get install postfix`. When installing `postfix`, you will see two prompts:
```
General type of mail configuration: Local Only
Domain Name: localhost.com (or whatever domain you chose.)
```

3. Create a virtual "catch all" email address by creating `/etc/postfix/virtual`. Once created, add these two lines:
```
@localhost <username>
@localhost.com <username>
```

If your local UNIX username is `testuser1` then replace `<username>` with that.

4. Modify the `postfix` configuration to allow virtual aliases. To do so add the following line to `/etc/postfix/main.cf`:
```
virtual_alias_maps = hash:/etc/postfix/virtual
```

NOTE: It is good practice to back up the `main.cf` configuration before making changes.

5. Run `sudo postmap /etc/postfix/virtual` to activate.

6. Reload `postfix` so that the above changes apply. To do so:
    `sudo service postfix reload`

7. Test that you are able to send an email! From the same client running the `postfix` server, run the following commands one at a time, and pressing <ENTER> after each one:
```
telnet localhost 25
helo localhost.com (or whatever domain you chose in step 2)
mail from: testuser1@localhost.com
rcpt to: doesntexist@localhost.com (this step will fail if step 4 & 5 were not done)
data
write something here
. (Just a period, and you should see a Queued message after this.)
quit
```

If all the steps above completed successfully, you should see something like this:
```
    qumulotest:src$ telnet localhost 25
    Trying 127.0.0.1...
    Connected to localhost.
    Escape character is '^]'.
    220 qumulotest.eng.qumulo.com ESMTP Postfix (Ubuntu)
    helo localhost.com
    250 qumulotest.eng.qumulo.com
    mail from: testuser1@localhost.com
    250 2.1.0 Ok
    rcpt to: bogusemail@localhost.com
    250 2.1.5 Ok
    data
    354 End data with <CR><LF>.<CR><LF>
    something in the body of the email
    .
    250 2.0.0 Ok: queued as 1E46BCA00D7
    quit
    221 2.0.0 Bye
    Connection closed by foreign host.
```

8. Install `mailutils` so that you can see if you're getting email:
    `sudo apt install mailutils`

    Once installed, just run `mail` to see if you were able to get the test email. Alternatively, you can try and `cat /var/spool/mail/<username>`.


If something went wrong and you'd like to retry, uninstall everything with:
```
sudo apt-get remove postfix
sudo apt-get purge postfix
```

Then reinstall `postfix` with:
    `sudo apt-get install postfix`

## Support Statement

This software is provided AS-IS and there is no specific SLA on response times on inquires regarding functionality, performance, or perceived software deficiencies. If you wish to report an issue, Please use GitHub Issues or your Qumulo Care Slack channel for assistance.

## Help

Use the [Issues](https://github.com/Qumulo/cluster-email-alerts/issues) section of this GitHub repo to post feedback or report bugs.

## Copyright

Copyright © 2023 [Qumulo, Inc.](https://qumulo.com)

## License

[![License](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)

See [LICENSE](LICENSE) for full details

```plaintext
MIT License

Copyright (c) 2022 Qumulo, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Trademarks

All other trademarks referenced herein are the property of their respective owners.

## Contributors

*   [Berat Ulualan](https://github.com/beratulualan)
*   [Michael Kade](https://github.com/mikekade)
