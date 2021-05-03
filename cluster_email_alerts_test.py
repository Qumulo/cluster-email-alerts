#!/usr/bin/env python3

import json
import os
import unittest

from parameterized import parameterized

from cluster_email_alerts import *

class LoadHelpersTest(unittest.TestCase):
    def setUp(self):
        self.test_file_name = "test_file"

    def tearDown(self):
        if os.path.exists(self.test_file_name):
            os.remove(self.test_file_name)

    def test_load_json_with_valid_json(self) -> None:
        json_dict = {
            'foo': 'bar',
            'baz': 'fug',
        }

        with open(self.test_file_name, 'w') as json_file:
            json.dump(json_dict, json_file)

        self.assertEqual(json_dict, load_json(self.test_file_name))

    def test_load_json_with_invalid_json_causes_sys_exit(self) -> None:
        with open(self.test_file_name, 'w') as bad_json_file:
            bad_json_file.write("foobar")

        with self.assertRaises(SystemExit):
            load_json(self.test_file_name)

    def test_load_config_with_existing_file(self) -> None:
        config_dict = {
            'important_switch': 'off',
            'destroy_all_data': True
        }

        with open(self.test_file_name, 'w') as json_file:
            json.dump(config_dict, json_file)

        self.assertEqual(config_dict, load_config(self.test_file_name))

    def test_load_config_without_existing_file_causes_sys_exit(self) -> None:
        with self.assertRaises(SystemExit):
            load_config(self.test_file_name)

    def test_load_history_with_existing_file(self) -> None:
        history_dict = {
            'quotas': 100,
            'capacity': 12,
            'replication': False
        }

        with open(self.test_file_name, 'w') as json_file:
            json.dump(history_dict, json_file)

        self.assertEqual(history_dict, load_history(self.test_file_name))

    def test_load_history_without_existing_file_returns_empty(self) -> None:
        default_history_dict = load_history(self.test_file_name)

        for key in ['quotas', 'capacity', 'replication']:
            self.assertIn(key, default_history_dict)

    def test_save_history_writes_to_file(self) -> None:
        history_dict = {
            'quotas': 100,
            'capacity': 12,
            'replication': False
        }

        save_history(self.test_file_name, history_dict)

        with open(self.test_file_name, 'r') as history_file:
            self.assertEqual(history_dict, json.load(history_file))

    def test_history_round_trip(self) -> None:
        history_dict = {
            'quotas': 100,
            'capacity': 12,
            'replication': False
        }

        save_history(self.test_file_name, history_dict)
        self.assertEqual(history_dict, load_history(self.test_file_name))


class HumanizeBytesHelperTest(unittest.TestCase):
    def test_truncate_to_tenths_place(self):
        self.assertEqual("1.2MB", humanize_bytes(1200000))
        self.assertEqual("1.2MB", humanize_bytes(1234567))

    def test_round_decimal(self):
        self.assertEqual("1.2KB", humanize_bytes(1250))
        self.assertEqual("1.3KB", humanize_bytes(1260))

    def test_specify_suffix(self):
        self.assertEqual("10.0 bytes", humanize_bytes(10, suffix=" bytes"))

    @parameterized.expand(
        [[''], ['K'], ['M'], ['G'], ['T'], ['P'], ['E'], ['Z'], ['Y']]
    )
    def test_suffix_scale(self, suffix: str):
        scale = 1
        if suffix == 'K':
            scale = 10 ** 3
        elif suffix == 'M':
            scale = 10 ** 6
        elif suffix == 'G':
            scale = 10 ** 9
        elif suffix == 'T':
            scale = 10 ** 12
        elif suffix == 'P':
            scale = 10 ** 15
        elif suffix == 'E':
            scale = 10 ** 18
        elif suffix == 'Z':
            scale = 10 ** 21
        elif suffix == 'Y':
            scale = 10 ** 24

        self.assertEqual(f'1.2{suffix}B', humanize_bytes(1.2 * scale))
        self.assertEqual(f'6.0{suffix}B', humanize_bytes(6 * scale))


class QuotasTest(unittest.TestCase):
    def setUp(self):
        self.config = {
            'quota_rules': {
                'a': { 'defined': 'defined rule' },
            },
            'default_quota_rules': {
                'undefined': 'undefined rule'
            }
        }

    def test_process_quotas_and_rules_empty(self):
        quotas = {}
        processed_quotas = process_quotas_and_rules(quotas, self.config)

        # Empty iterables evaluate to false
        self.assertFalse(processed_quotas)

    def test_process_quotas_and_rules_defined(self):
        quotas = {
            'a': { 'provided': 'provided rule' },
        }

        processed_quotas = process_quotas_and_rules(quotas, self.config)
        processed_quota = processed_quotas['a']

        for word in ['provided', 'defined']:
            self.assertIn(word, processed_quota)
        self.assertNotIn('undefined', processed_quota)

    def test_process_quotas_and_rules_undefined(self):
        quotas = {
            'none': { 'provided': 'provided rule' },
        }

        processed_quotas = process_quotas_and_rules(quotas, self.config)
        processed_quota = processed_quotas['none']

        for word in ['provided', 'undefined']:
            self.assertIn(word, processed_quota)
        self.assertNotIn('defined', processed_quota)


if __name__ == "__main__":
    unittest.main()
