# 🛰️ Wi-Fi Jammer -  Deauthentication Tool

> **⚠️ DISCLAIMER: FOR AUTHORIZED SECURITY TESTING AND EDUCATIONAL PURPOSES ONLY**

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Linux-lightgrey.svg)



## Overview

Wi-Fi Jammer is a Python-based tool designed to disconnect devices such as Phones, Laptops, CCTV's, Smart locks, etc which are connected to Wi-Fi. Tool also supports single Wi-Fi jamming, multiple Wi-Fi jamming and jamming all the available Wi-Fi's in range

**Purpose**: This tool is intended for:
- Security researchers testing their own networks
- Penetration testers with proper authorization
- Educational demonstrations of Wi-Fi vulnerabilities
- Network administrators testing intrusion detection systems



## ✨ Features

### 🎯 Targeted Attack Modes
- **Single AP Attack**: Target individual Wi-Fi networks
- **Multiple AP Attack**: Select and attack multiple networks sequentially
- **All APs Attack**: Comprehensive channel-based attack on all detected networks

### 🔍 Network Discovery
- Automatic Wi-Fi network scanning
- Detailed AP information display (ESSID, BSSID, Channel, Signal, Clients)
- Real-time network monitoring using airodump-ng

### ⚡ Advanced Capabilities
- Intelligent channel switching
- Signal strength-based attack prioritization
- Concurrent deauthentication attacks
- Graceful cleanup and process management


## 🔧 Prerequisites

### System Requirements
- **Operating System**: Linux (Kali Linux recommended)
- **Python**: Version 3.8 or higher
- **Root Privileges**: Required for wireless interface manipulation
- **Wi-Fi Adapter** - Use Wi-Fi adapter for scanning long range and better attacking, optional if using laptop
<p align="center">
  <a href="https://www.amazon.in/TP-Link-Wireless-Network-Supports-T2U/dp/B07P681N66?source=ps-sl-shoppingads-lpcontext&ref_=fplfs&smid=AJ6SIZC8YQDZX&th=1">
    <img src="https://m.media-amazon.com/images/I/51ii8SWvsPL._SL1500_.jpg" width="300">
  </a>
  <a href="https://www.amazon.in/Long-Range-Dual-Band-Wireless-External-Antennas/dp/B00VEEBOPG?source=ps-sl-shoppingads-lpcontext&ref_=fplfs&psc=1&smid=A7TY3KN2D336C">
    <img src="https://m.media-amazon.com/images/I/41Qo0EGG4TL._SL1000_.jpg" width="300">
  </a>
</p>

### 🛠️ Required Tools
**The following must be installed on your system:**
- python3, aircrack-ng, wireless-tools iw

```bash
sudo chmod +x setup.sh
sudo ./setup.sh 
```


📦 Installation
---------------

### Download

```bash

# Clone the repository
git clone https://github.com/udayXXkumar/wifi-jammer.git
cd wifi-jammer

# Make executable
chmod +x wifi_Jammer.py

# Run with root privileges
sudo ./wifi_Jammer.py
```


🚀 Usage
--------

### Basic Usage

```bash

# Start the tool (default interface wlan0)
sudo ./wifi_Jammer.py

# Specify custom wireless interface
sudo ./wifi_Jammer.py --iface wlan1

# Set custom cycle time for "all" mode
sudo ./wifi_Jammer.py --time 180

# To display help message
sudo ./wifi_Jammer.py -h

```


### ⚙️ Attack Modes

#### 1\. **Single AP Attack** (s)

-   Target one specific Wi-Fi network

-   Customizable attack duration

-   Channel auto-switching

#### 2\. **Multiple AP Attack** (m)

-   Select multiple networks

-   Sequential attacks

-   Configurable duration per AP

#### 3\. **All APs Attack** (a)

-   Attack all detected networks

-   Intelligent channel scheduling

-   Weighted by signal strength and AP count


🎯 How It Works
---------------

### Technical Workflow

1\.  **Monitor Mode Setup**

    -   Kills conflicting network processes

    -   Enables monitor mode on wireless interface

    -   Configures interface for packet injection

2\.  **Network Discovery**

    -   Uses `airodump-ng` for comprehensive scanning

    -   Parses CSV output for AP details

    -   Maps clients to their associated APs

3\.  **Attack Execution**

    -   Sets appropriate channel

    -   Executes deauthentication frames using `aireplay-ng`

    -   Manages multiple concurrent processes

    -   Implements intelligent timing and scheduling

4\.  **Cleanup**

    -   Terminates all attack processes

    -   Restores wireless interface to managed mode

    -   Re-enables network services

## 💀 Attack Methodology
-   **Deauthentication Frames**: Sends IEEE 802.11 deauth packets

-   **Channel Switching**: Dynamically changes channels to target multiple APs

-   **Process Management**: Thread-safe process handling for concurrent attacks



## 🧪 Tested On
- Kali Linux
- Ubuntu 22.04
- Parrot OS


## 🤝 Contributing

- Fork the repository
- Create a feature branch (git checkout -b feature/AmazingFeature)
-  Commit your changes (git commit -m 'Add AmazingFeature')
- Push to the branch (git push origin feature/AmazingFeature)

- Open a Pull Request


## ⭐ Support

If you find this project useful:
- ⭐ Star the repository
- 🐞 Report bugs
- 💡 Suggest features

⚠️ Warning
----------

**This tool can:**

-   Disrupt legitimate network traffic

-   Cause service interruption

-   Trigger intrusion detection systems

-   Potentially violate laws if used improperly

---


**Created for educational purposes** - **Use responsibly** - **Always get permission**
> **Knowledge is power — use it ethically.**




