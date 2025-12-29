#!/bin/bash
# setup.sh - Enhanced Installation script for Wi-Fi Jammer

set -e  # Exit on error

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}==========================================${NC}"
echo -e "${YELLOW}  Wi-Fi Jammer Installation${NC}"
echo -e "${YELLOW}==========================================${NC}"
echo ""

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: Please run with sudo${NC}"
    echo "Usage: sudo ./setup.sh"
    exit 1
fi

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo -e "${RED}Error: This tool only works on Linux${NC}"
    exit 1
fi

# Update package list
echo -e "${YELLOW}[1/4] Updating package list...${NC}"
apt-get update -q

# Install dependencies
echo -e "${YELLOW}[2/4] Installing dependencies...${NC}"
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    aircrack-ng \
    python3 \
    python3-pip \
    wireless-tools \
    iw

# Check installation
echo -e "${YELLOW}[3/4] Verifying installations...${NC}"
if command -v python3 &> /dev/null && command -v aireplay-ng &> /dev/null; then
    echo -e "${GREEN}✓ All dependencies installed successfully${NC}"
else
    echo -e "${RED}✗ Some dependencies failed to install${NC}"
    exit 1
fi

# Make main script executable
echo -e "${YELLOW}[4/4] Setting up permissions...${NC}"
if [ -f "wifi_Jammer.py" ]; then
    chmod +x wifi_Jammer.py
    echo -e "${GREEN}✓ Made wifi_Jammer.py executable${NC}"
else
    echo -e "${YELLOW}⚠ wifi_Jammer.py not found in current directory${NC}"
fi

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo -e "To use Wi-Fi Jammer:"
echo -e "  ${YELLOW}sudo ./wifi_Jammer.py${NC}"
echo ""
echo -e "${RED}⚠  LEGAL DISCLAIMER:${NC}"
echo -e "This tool is for AUTHORIZED security testing only."
echo -e "Use only on networks you own or have permission to test."
echo ""