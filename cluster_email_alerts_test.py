#!/usr/bin/env python3

import json
import os
import unittest

from cluster_email_alerts import load_json

class HelperTest(unittest.TestCase):
    def setUp(self):
        self.test_file_name = "test_file"

    def tearDown(self):
        if os.path.exists(self.test_file_name):
            os.remove(self.test_file_name)

    def test_load_json_happy_case(self) -> None:
        json_dict = {
            'foo': 'bar',
            'baz': 'fug',
        }

        with open(self.test_file_name, 'w') as json_file:
            json.dump(json_dict, json_file)

        self.assertEqual(json_dict, load_json(self.test_file_name))

    def test_load_json_invalid_json_causes_sys_exit(self) -> None:
        with open(self.test_file_name, 'w') as bad_json_file:
            bad_json_file.write("foobar")

        with self.assertRaises(SystemExit):
            load_json(self.test_file_name)


if __name__ == "__main__":
    unittest.main()
