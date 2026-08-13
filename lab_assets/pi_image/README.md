# Golden Image Creation v2.0

This document outlines the process for creating a golden image to flash to a Raspberry Pi 4B for use in a distributed robotics platform for ECGR 4161: Intro to Robotics.

A golden image is a master operating system template pre-configured with required software, dependencies, and settings. Rather than manually setting up Ubuntu, ROS 2, and networking on each robot, you configure one reference Pi, capture its exact state, and flash that image to many SD cards.

**Pipeline Overview:**

1. **The Foundation (Phases 1 and 2):** Start from a fresh Ubuntu Server install, define network behavior, and install robotics toolchains.
2. **The Scrub (Phase 3):** Remove machine-specific identity data so each cloned Pi generates unique IDs and keys on first boot.
3. **Capture and Compression (Phases 4 and 5):** Clone the cleaned SD card image and shrink it using PiShrink for easy distribution.

---

## Required Materials

- 32GB SD card
- Raspberry Pi 4B (with appropriate power supply)
- Wired internet connection (Ethernet)
- Windows laptop (with SD reader/adapter)

---

## Phase 1: Clean Installation

### Ubuntu Flash

1. Install Raspberry Pi Imager.
2. Mount SD card in Windows.
3. Open Raspberry Pi Imager.
4. Flash the SD card.

### Pre-Boot Configuration

1. Pi Imager usually ejects the drive automatically after flashing. Remount the drive.
2. Open the drive in Windows File Explorer.
3. Find the file named `network-config` and set it to:

```yaml
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      dhcp6: true
      optional: true
    wlan0:
      dhcp4: false
      addresses: [192.168.4.1/24]
```

4. Save the file.
5. Find the file named `user-data`.
6. You may now eject the drive.

---

## Phase 2: Pi Ubuntu Setup

### First Boot

1. Insert your SD card into the Pi.
2. Insert your internet-connected Ethernet cable into the Pi.
3. Supply power to the Pi.
4. Wait a few minutes for boot completion.
5. SSH into the Pi using `ssh <user>@<hostname>.local`.

### ROS 2 Installation

Follow the [ROS 2 Humble Installation Guide for Ubuntu](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html) (recommended), or use the commands below.

1. Update system packages:

```bash
sudo apt update && sudo apt upgrade -y
```

2. Verify locale supports UTF-8 using `locale`.
3. Ensure the Ubuntu Universe repository is enabled.
4. Install ROS apt source package:

```bash
sudo apt update && sudo apt install curl -y
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F\" '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb \
  "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo ${UBUNTU_CODENAME:-${VERSION_CODENAME}})_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
```

5. Update and upgrade again:

```bash
sudo apt update && sudo apt upgrade -y
```

6. Install base ROS 2:

```bash
sudo apt install ros-humble-ros-base
```

7. Install ROS 2 dev tools:

```bash
sudo apt install ros-dev-tools
```

8. Install example nodes:

```bash
sudo apt install ros-humble-demo-nodes-cpp ros-humble-demo-nodes-py
```

9. Source ROS 2 automatically for new terminals (run once):

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
```

### Romi Interface Setup

#### I2C Setup

1. The OS should boot with I2C enabled, but verify manually.
2. Open config:

```bash
sudo nano /boot/firmware/config.txt
```

3. Verify I2C settings are present/enabled.

#### Pololu I2C Slave Software

1. Install required Python dependencies:

```bash
sudo apt-get install python3 python3-flask python3-smbus
```

2. Download Pololu library:

```bash
wget https://github.com/pololu/pololu-rpi-slave-arduino-library/archive/<version>.tar.gz
tar -xzf <version>.tar.gz
mv pololu-rpi-slave-arduino-library-<version> pololu-rpi-slave-arduino-library
```

### Wireless AP Configuration

The packages installed at boot (net-tools, iw, hostapd, and dnsmasq) are used in this section.

1. Stop and disable AP services:

```bash
sudo systemctl stop hostapd dnsmasq
sudo systemctl disable hostapd dnsmasq
```

2. Edit dnsmasq config:

```bash
sudo nano /etc/dnsmasq.conf
```

3. Write:

```
interface=wlan0
bind-interfaces
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
```

4. Edit hostapd config:

```bash
sudo nano /etc/hostapd/hostapd.conf
```

5. Paste:

```
interface=wlan0
driver=nl80211
ssid=MyRomiNetwork
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=romi
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=US
```

6. Set hostapd default config:

```bash
sudo nano /etc/default/hostapd
```

Ensure this line exists and is uncommented:

```
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

7. Edit netplan config:

```bash
sudo nano /etc/netplan/50-cloud-init.yaml
```

8. Paste:

```yaml
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      dhcp6: true
      optional: true
    wlan0:
      dhcp4: false
      addresses: [192.168.4.1/24]
```

9. Edit systemd-resolved config:

```bash
sudo nano /etc/systemd/resolved.conf
```

10. Set:

```
DNSStubListener=no
```

11. Create startup script for dynamic SSID/channel:

```bash
#!/bin/bash
# MAKE SURE TO RUN THE FOLLOWING AFTER SAVING THIS FILE
# sudo chmod +x /usr/local/bin/update_wifi.sh

# 1. Get the MAC and create the unique SSID
FULL_MAC=$(cat /sys/class/net/wlan0/address | tr -d ':')
SHORT_ID=${FULL_MAC: -4}
NEW_SSID="Romi-$SHORT_ID"

# 2. Pick a random clean channel (1, 6, or 11)
NEW_CHANNEL=$(printf "1\n6\n11" | shuf -n 1)

# 3. Apply changes to hostapd.conf
sed -i "s/^ssid=.*/ssid=$NEW_SSID/" /etc/hostapd/hostapd.conf
sed -i "s/^channel=.*/channel=$NEW_CHANNEL/" /etc/hostapd/hostapd.conf

# 4. Log the result
echo "[$(date)] SSID=$NEW_SSID CHANNEL=$NEW_CHANNEL" >> /var/log/robot_wifi.log
```

12. Configure startup cron job:

```bash
sudo crontab -e
```

13. Add:

```
@reboot sleep 5; netplan apply && /bin/bash /usr/local/bin/update_wifi.sh && systemctl restart hostapd dnsmasq
```

14. Unmask hostapd:

```bash
sudo systemctl unmask hostapd
```

---

## Phase 3: Sanitize the Build for Cloning

### Clear Package and Workspace Artifacts

1. Clean apt cache and unnecessary dependencies:

```bash
sudo apt-get autoremove --purge -y; sudo apt-get clean
```

2. Clear temporary files:

```bash
sudo rm -rf /tmp/* /var/tmp/*
```

### System Identity and Log Wipe

1. Truncate logs:

```bash
sudo find /var/log -type f -exec truncate -s 0 {} +
```

2. Wipe machine-id and reset dbus link:

```bash
sudo truncate -s 0 /etc/machine-id
sudo rm /var/lib/dbus/machine-id
sudo ln -s /etc/machine-id /var/lib/dbus/machine-id
```

3. Remove unique SSH host keys:

```bash
sudo rm -f /etc/ssh/ssh_host_*
```

### Cloud-Init and Network Reset

1. Disable cloud-init network overwrite:

```bash
echo "network: {config: disabled}" | sudo tee /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
```

2. Clean cloud-init logs and seed state:

```bash
sudo cloud-init clean --logs --seed
```

3. Remove instance-specific cloud-init data:

```bash
sudo rm -rf /var/lib/cloud/instances/*
```

4. Final shutdown prep:

```bash
cat /dev/null > ~/.bash_history && history -c && sudo shutdown -h now
```

---

## Phase 4: Cloning Disk Image

1. Remove SD card from the Pi.
2. Mount SD card in Windows.
3. Install Win32 Disk Imager.
4. Use Win32 Disk Imager to clone the SD card to an image file and note where you save it.

---

## Phase 5: Final Packaging (Shrink Image)

1. Install PiShrink in WSL:

```bash
sudo apt update && sudo apt install -y wget parted gzip pigz xz-utils udev e2fsprogs
wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
chmod +x pishrink.sh
sudo mv pishrink.sh /usr/local/bin
```

2. Move clone image into WSL home directory:

```bash
sudo mv <path to your clone> ~
```

3. Shrink filesystem image:

```bash
sudo pishrink.sh -a <clone file>
```

The resulting image should shrink to under 10GB and is ready for distribution.

> **Important:** Perform sanitization steps exactly before cloning. Skipping identity cleanup can cause duplicate host keys, network conflicts, and difficult-to-debug multi-robot failures.

Recommended contents:

- `ClassPiImage-ubuntu22.04.img.xz` (or your official class image filename)
- `ClassPiImage-ubuntu22.04.sha256`
- `RELEASE_NOTES.md` (what changed between image versions)

Suggested release workflow:

1. Compress the image (`.img.xz`) before sharing.
2. Publish a SHA256 checksum for integrity verification.
3. Include a short changelog for students and TAs.

Flashing summary (Raspberry Pi Imager):

1. Device: Raspberry Pi 4.
2. OS: Use Custom (select the class image).
3. Storage: target microSD card.
4. Flash and eject safely.
