ZeroShell connect
===

This script allows for automatic logging on the [Captive Portal](https://zeroshell.org/shibboleth-captive-portal/) of the Linux
Distribution [Zeroshell](https://zeroshell.org).

This was inspired from this [zeroshell-autologin](https://code.google.com/archive/p/zeroshell-autologin/) python script.

# How to install

### Global install
```
pip3 install --user -r requirements.txt
```

### Virtualenv install
```
pip3 install virtualenv
python3 -m venv venv
source ./venv/bin/activate
pip3 install -r requirements.txt
```

# How to use

The configuration is done by editting the full caps variables at the top of the
`connect.py` file.

```
python3 ./connect.py [--renew] [--verbose] [--output FILE]
```

# Run it as a background service

Having to run the tool manually can be fun at first but it gets really annoying
over time. Here is how to add it as a **systemd** service.

Before doing anything, make sure you have installed all the python requirements
by following the instructions in **How to install > Global Install**.

Make sure the python file is accessible and executable by the system:
```
sudo cp connect.py /root/zeroshell_connect.py
sudo chmod u+x /root/zeroshell_connect.py
```

Edit the service file at `/etc/systemd/system/zeroshellconnect.service`:
```
[Unit]
Description = Login through Zeroshell network
After = network.target

[Service]
ExecStart = /usr/bin/python3 /root/zeroshell_connect.py --output /var/log/zeroshell_connect.log

[Install]
WantedBy = multi-user.target
```

Enable the service to make it start upon startup and start it:
```
systemctl enable zeroshellconnect.service
systemctl start zeroshellconnect.service
```

Check that everything went well:
```
systemctl status zeroshellconnect.service
```

# Authors

* Marc Villain (marc.villain@epita.fr)
