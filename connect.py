import argparse
import datetime
import ssl
import sys
from functools import wraps
from html.parser import HTMLParser
from time import sleep
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import logging
from logging.handlers import RotatingFileHandler
import subprocess

from bs4 import BeautifulSoup

# Configuration
# -------------

# Your credentials
USERNAME = "PUT_YOUR_USERNAME_HERE"
PASSWORD = "PUT_YOUR_PASSWORD_HERE"
# Time in seconds between each login renewal
RENEW_INTERVAL = 40
# Time in seconds between login retry when connection is lost
LOGIN_RETRY_INTERVAL = 10
# Link to connection URL
ZSCP_URL = "https://PUT_ROOTER_IP_HERE:12081/cgi-bin/zscp"
ZSCP_REDIRECT = "_:::_"
# Realm to connect to (if you try to access the router url while
# not being connected, you should find the realm in the scrolling menu)
REALM = "PUT_YOUR_REALM_HERE"


# Get logger
# ----------
logger = logging.getLogger()


# Useful classes to manipulate requests
# -------------------------------------
def msg_then_done(msg):
    def decorator(func):
        @wraps(func)
        def _msg_then_done(*args, **kwargs):
            logger.info(msg + "...Running")
            ret_val = func(*args, **kwargs)
            logger.info(msg + "...Done")
            return ret_val
        return _msg_then_done
    return decorator

class Parametor:
    """
    Helps to build the required parameters before doing
    any request to the server.
    """
    @staticmethod
    def _gen_default():
        return {"ZSCPRedirect": ZSCP_REDIRECT}

    @classmethod
    def _gen_default_user(cls):
        params = cls._gen_default()
        params["U"] = USERNAME
        params["P"] = PASSWORD
        params["Realm"] = REALM
        return params

    @classmethod
    def gen_retrieve_auth_key(cls):
        params = cls._gen_default_user()
        params["Section"] = "CPAuth"
        params["Action"] = "Authenticate"
        return params

    @classmethod
    def gen_cpgw(cls, auth_key):
        params = cls._gen_default_user()
        params["Authenticator"] = auth_key
        params["Section"] = "CPGW"
        params["Action"] = "Connect"
        return params

    @classmethod
    def gen_client_ctrl(cls, auth_key):
        params = cls._gen_default_user()
        params["Authenticator"] = auth_key
        params["Section"] = "ClientCTRL"
        params["Action"] = "Connect"
        return params

    @classmethod
    def gen_renew(cls, auth_key):
        params = cls._gen_default()
        params["Authenticator"] = auth_key
        params["Section"] = "CPGW"
        params["Action"] = "Renew"
        return params


class MyRequest:
    """
    Handle all the requests to the server.
    """
    def __init__(self):
        self.url = ZSCP_URL
        self.auth_key = None

    def _call(self, params, url=None):
        if not url:
            url = self.url

        encoded_data = urlencode(params).encode("ascii")
        req = Request(url, encoded_data)
        http_req = urlopen(req, context=ssl._create_unverified_context())
        response = http_req.read()

        soup = BeautifulSoup(response, "html.parser")
        messages = [elt.text for elt in soup.find_all("font")]

        return messages, response

    def _messages_contains(self, messages, message):
        if len(messages) == 0:
            return False
        if message not in messages:
            logger.debug(messages)
            return False
        return True

    def _messages_not_contains(self, messages, message):
        return not self._messages_contains(messages, message)

    @msg_then_done("Retrieve auth key")
    def call_retrieve_auth_key(self):
        params = Parametor.gen_retrieve_auth_key()
        messages, content = self._call(params)
        if not self._messages_contains(messages, "Connecting to the Network..."):
            return False

        # Extract auth key from hidden inputs
        soup = BeautifulSoup(content, 'html.parser')
        hidden_tags = soup.find_all(name="input", type="hidden")
        for tag in hidden_tags:
            if tag.get("name") == "Authenticator":
                self.auth_key = tag.get("value")

        return True

    @msg_then_done("Connect control panel gateway")
    def call_cpgw(self):
        params = Parametor.gen_cpgw(self.auth_key)
        messages, content = self._call(params)
        return self._messages_not_contains(messages, "Access Denied !!!")

    @msg_then_done("Connect client control")
    def call_client_ctrl(self):
        params = Parametor.gen_client_ctrl(self.auth_key)
        messages, content = self._call(params)
        return self._messages_contains(messages, "")

    @msg_then_done("Renew control panel gateway")
    def call_renew(self):
        params = Parametor.gen_renew(self.auth_key)
        messages, content = self._call(params)
        return self._messages_contains(messages, "")


# Main function and its helpers
# -----------------------------
def raise_on_fail(proc, *args, **kwargs):
    if not proc(*args, **kwargs):
        raise Exception(f"Function {str(proc)} failed.")


def count_down(counter=0, msg=""):
    while counter > 0:
        logger.info(f"{msg} in: {str(counter)}s")
        sleep(10)
        counter -= 10


def setup_logging(verbose, silent, output):
    log_level = logging.DEBUG if verbose else logging.INFO

    # Setup format
    logger.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')

    # Setup file logging
    if output:
        file_handler = RotatingFileHandler(output, 'a', 1000000, 1)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Setup stdout logging
    if not silent:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)
        logger.addHandler(stream_handler)


def main(args):
    setup_logging(args.verbose, args.silent, args.output)

    req = MyRequest()

    # Keep running no matter what
    while True:
        try:
            # Retrieve auth key
            raise_on_fail(req.call_retrieve_auth_key)

            # Log in
            try:
                raise_on_fail(req.call_cpgw)
                raise_on_fail(req.call_client_ctrl)
            except:
                pass  # Already connected

            # Keep on trying to renew connection until something goes wrong
            while True:
                # Check if we have Internet access
                if subprocess.call(['ping', '-c', '1', '8.8.8.8']) != 0:
                    raise Exception("No Internet Access")

                # Renew connection
                count_down(RENEW_INTERVAL, "Next renewal")
                raise_on_fail(req.call_renew)

        except Exception as e:
            # If anything went wrong, consider it as a login failure and keep
            # on trying to login again
            logger.error(e)
            count_down(LOGIN_RETRY_INTERVAL, "Login failed. Retrying")


def parse_command_line(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true", help="Set logging level to DEBUG.")
    parser.add_argument("-s", "--silent", action="store_true", help="Do not log to stdout.")
    parser.add_argument("-o", "--output", metavar="FILE", help="Log to file.")
    return parser.parse_args(argv[1:])


if __name__ == "__main__":
    args = parse_command_line(sys.argv)
    main(args)
