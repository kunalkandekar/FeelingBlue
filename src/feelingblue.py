# performs a simple device inquiry, followed by a remote name request of each
# discovered device

import os
import sys
import struct
import time
import threading
import subprocess
    
#util methods
def printpacket(pkt):
    for c in pkt:
        sys.stdout.write("%02x " % struct.unpack("B",c)[0])
    print 


#abstract class
class BluetoothInterface():
    def __init__(self):
        pass
        
    def get_rssi(self, selected_addr):
        pass
        
    def get_devices(self):
        pass

#Bluez interface (Linux and Windows)
class BluezInterface(BluetoothInterface):
    def __init__(self):
        super.__init__(self)
        import bluetooth._bluetooth as bluez
        from bluetooth import lookup_name
        self.sock = None

    def read_inquiry_mode(self, sock):
        """returns the current mode, or -1 on failure"""
        # save current filter
        old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)
    
        # Setup socket filter to receive only events related to the
        # read_inquiry_mode command
        flt = bluez.hci_filter_new()
        opcode = bluez.cmd_opcode_pack(bluez.OGF_HOST_CTL, 
                bluez.OCF_READ_INQUIRY_MODE)
        bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
        bluez.hci_filter_set_event(flt, bluez.EVT_CMD_COMPLETE);
        bluez.hci_filter_set_opcode(flt, opcode)
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt )
    
        # first read the current inquiry mode.
        bluez.hci_send_cmd(sock, bluez.OGF_HOST_CTL, 
                bluez.OCF_READ_INQUIRY_MODE )
    
        pkt = sock.recv(255)
    
        status,mode = struct.unpack("xxxxxxBB", pkt)
        if status != 0: mode = -1
    
        # restore old filter
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, old_filter )
        return mode
    
    def write_inquiry_mode(self, sock, mode):
        """returns 0 on success, -1 on failure"""
        # save current filter
        old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)
    
        # Setup socket filter to receive only events related to the
        # write_inquiry_mode command
        flt = bluez.hci_filter_new()
        opcode = bluez.cmd_opcode_pack(bluez.OGF_HOST_CTL, 
                bluez.OCF_WRITE_INQUIRY_MODE)
        bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
        bluez.hci_filter_set_event(flt, bluez.EVT_CMD_COMPLETE);
        bluez.hci_filter_set_opcode(flt, opcode)
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt )
    
        # send the command!
        bluez.hci_send_cmd(sock, bluez.OGF_HOST_CTL, 
                bluez.OCF_WRITE_INQUIRY_MODE, struct.pack("B", mode) )
    
        pkt = sock.recv(255)
    
        status = struct.unpack("xxxxxxB", pkt)[0]
    
        # restore old filter
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, old_filter )
        if status != 0: return -1
        return 0
    
    def device_inquiry_with_with_rssi(self, sock, selected_addr=None):
        # save current filter
        old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)
    
        # perform a device inquiry on bluetooth device #0
        # The inquiry should last 8 * 1.28 = 10.24 seconds
        # before the inquiry is performed, bluez should flush its cache of
        # previously discovered devices
        flt = bluez.hci_filter_new()
        bluez.hci_filter_all_events(flt)
        bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt )
    
        duration = 4
        max_responses = 255
        cmd_pkt = struct.pack("BBBBB", 0x33, 0x8b, 0x9e, duration, max_responses)
        bluez.hci_send_cmd(sock, bluez.OGF_LINK_CTL, bluez.OCF_INQUIRY, cmd_pkt)
    
        results = []
    
        done = False
        while not done:
            pkt = sock.recv(255)
            ptype, event, plen = struct.unpack("BBB", pkt[:3])
            #print "packet type 0x%02x event 0x%02x" % (ptype, event)
            if event == bluez.EVT_INQUIRY_RESULT_WITH_RSSI:
                pkt = pkt[3:]
                nrsp = struct.unpack("B", pkt[0])[0]
                for i in range(nrsp):
                    addr = bluez.ba2str( pkt[1+6*i:1+6*i+6] )
                    rssi = struct.unpack("b", pkt[1+13*nrsp+i])[0]
                    if selected_addr:
                        if selected_addr == addr:
                            results.append( ( addr, rssi) )
                            break
                    else:
                        results.append( ( addr, rssi) )
                    #print "[%s] RSSI: [%d]" % (addr, rssi)
            elif event == bluez.EVT_INQUIRY_COMPLETE:
                done = True
            elif event == bluez.EVT_CMD_STATUS:
                status, ncmd, opcode = struct.unpack("BBH", pkt[3:7])
                if status != 0:
                    print "uh oh..."
                    printpacket(pkt[3:7])
                    done = True
            else:
                print "unrecognized packet type 0x%02x" % ptype
    
    
        # restore old filter
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, old_filter )
        return results
        
    def lookup_names(self, results):
        named_results = []
        addr_map = dict()
        for (addr, rssi) in results:    #get unique addrs
            addr_map[addr] = rssi   #choose the smallest one?
        for addr, rssi in addr_map.iteritems():
            name = lookup_name(addr)
            named_results.append( ( name, addr, rssi) )
        return named_results
    
    def open_bt_sock():
        dev_id = 0
        try:
            sock = bluez.hci_open_dev(dev_id)
        except:
            print "error accessing bluetooth device..."
            sys.exit(1)
        return sock
    
    def get_rssi(self, selected_addr = None):
        if self.sock: self.sock.close()
        self.sock = BluezInterface.open_bt_sock()
        try:
            mode = self.read_inquiry_mode(sock)
        except Exception, e:
            print "error reading inquiry mode.  "
            print "Are you sure this a bluetooth 1.2 device?"
            print e
            sys.exit(1)
        #print "current inquiry mode is %d" % mode
    
        if mode != 1:
            print "writing inquiry mode..."
            try:
                result = self.write_inquiry_mode(sock, 1)
            except Exception, e:
                print "error writing inquiry mode.  Are you sure you're root?"
                print e
                sys.exit(1)
            if result != 0:
                print "error while setting inquiry mode"
            print "result: %d" % result
    
        return self.device_inquiry_with_with_rssi(self.sock, selected_addr)
    
    def get_devices(self):
        raw_results = self.get_rssi(None)
        results = self.lookup_names(raw_results)
        return results

#IOBluetoothInterface (Mac OS X)
class IOBluetoothInterface():
    def __init__(self):
        pass
        
    def get_rssi(self, selected_addr):
        pass
        
    def get_devices(self):
        pass

def run_shell_cmd(proximity_cmd):
    print 'Running [',proximity_cmd, '] in shell'
    subprocess.call(proximity_cmd, shell=True)
    return

class BluetoothManager(threading.Thread):
    def __init__(self):
        #only monitoring one device at a time for now...
        self.selected_device = None
        self.selected_rssi   = 0
        self.selected_addr   = None
        self.calibrated_rssi = 0
        self.is_calibrated   = False
        self.tolerance_ratio = 0.2
        self.in_proximity    = False
        #TODO: Make this user-configurable
        #run on kunal-kandekars-macbook-pro.local 'synergys -f -c ~/Documents/utils/synergy-plus-1.3.4/synergy.conf'
        self.in_proximity_cmd       = 'synergyc -f kunal-kandekars-macbook-pro.local'
        self.out_of_proximity_cmd   = 'killall synergyc'
        self.poll_interval_msec = 2000
        self.done = False
        self.btif = None
        
        #init the right interface
        import sys
        if sys.platform == 'darwin':
            self.btif = OSXIOBluetoothInterface()
        else:
            self.btif = BluezInterface()
        
        threading.Thread.__init__ (self)

    def reset(self):
        self.selected_device = None
        self.selected_rssi   = 0
        self.selected_addr   = None
        self.calibrated_rssi = 0
        self.is_calibrated   = False
        self.in_proximity    = False

    def set_selected_device(self, name, addr):
        self.selected_device = name
        self.selected_addr   = addr
        
    def get_devices(self):
        return self.btif.get_devices()

    def calibrate(self):
        #raw_results = get_rssi(self.sock)
        #named_results = self.lookup_names(raw_results)
        #results = [(name,addr,rssi) for (name,addr,rssi) in named_results if name == self.selected_device]
        results = self.btif.get_rssi(self.selected_addr)
        if len(results) < 1: 
            self.selected_device = None
            return
        (addr,rssi) = results[0]
        self.calibrated_proximity_rssi = self.selected_rssi = rssi
        print 'Proximity RSSI calibrated to ', self.calibrated_proximity_rssi
        self.is_calibrated = True

    def run(self):
        self.done = False
        self.stateChange = False

        while not self.done: #
            if self.selected_device and self.is_calibrated:
                results = self.btif.get_rssi(self.selected_addr)
                #results = [(addr,rssi) for (addr,rssi) in raw_results if addr == selected_addr]
                if len(results):
                    (addr,rssi) = results[0]
                    self.selected_rssi = rssi
                    if not self.in_proximity:
                        if rssi >= self.calibrated_proximity_rssi * (1 + self.tolerance_ratio):
                            print self.selected_device, ' detected to be in proximity (',rssi,\
                                '>= ',self.calibrated_proximity_rssi, '-', \
                                self.calibrated_proximity_rssi * (1 + self.tolerance_ratio), ')'
                            self.in_proximity = True
                            if (self.in_proximity_cmd): 
                                run_shell_cmd(self.in_proximity_cmd)
                        #endif rssi
                    else:   #if in_proxmity
                        if rssi < self.calibrated_proximity_rssi * (1 + self.tolerance_ratio):
                            print self.selected_device, ' detected to be out of proximity (',rssi,\
                                '< ',self.calibrated_proximity_rssi, '-', \
                                self.calibrated_proximity_rssi * (1 + self.tolerance_ratio), ')'
                            self.in_proximity = False
                            if (self.out_of_proximity_cmd): 
                                run_shell_cmd(self.out_of_proximity_cmd)
                        #endif rssi
                    #end if in_proximity
                else: # selected bluetooth devices not detected, assume gone away
                    print self.selected_device+ '@' +self.selected_addr, 'not detected...' #, stopping...'
                #    self.reset()
                #end if len
            #end if selected_device
            #print 'sleeping for', int(self.poll_interval_msec/1000), 'secs'
            time.sleep(int(self.poll_interval_msec/1000))
            #if self.done: print "DONE!"
            #print 'woke up after', int(self.poll_interval_msec/1000), 'secs'
        #end while
        print 'DONE!'

class Console:
    def __init__(self, bt):
        self.btmgr = bt
        pass
        
    def list_and_get_devices(self):
        results = self.btmgr.get_devices()
        index = 1
        for (name, addr, rssi) in results:
            print '%d: %s [%d]: %s' %(index, addr, rssi, name)
            index += 1
        return results        
        
    def run(self):
        while True:
            if self.btmgr.selected_device:  #we're already monitoring a device, present some options
                if not self.btmgr.is_calibrated:
                    raw_input('Bring selected device ' + self.btmgr.selected_device+' in proximity, then press enter: ')
                    self.btmgr.calibrate()
                    continue
                cmd = raw_input('Press q to quit, r to recalibrate, u to unselect device, l to list devices: ')
                if cmd == 'u':
                    #self.btmgr.pause()
                    self.btmgr.selected_device = None #non-critical app, not giving a hoot about locks and concurrency
                elif cmd == 'q':
                    self.btmgr.done = True
                    break
                elif cmd == 'r':
                    self.btmgr.is_calibrated = False
                elif cmd == 'l':
                    self.list_and_get_devices()
            else:   #we don't have a device to monitor, ask user if they'd like to select one
                print 'Detected Bluetooth devices:'
                results = self.list_and_get_devices()
                cmd = raw_input('Select a device number (or r to refresh, enter q to quit): ')
                if cmd == 'q': break
                if cmd == 'r': continue
                try :
                    selected = int(cmd)
                    if selected > len(results):
                        print 'invalid selection'
                    else:
                        self.btmgr.set_selected_device(results[selected - 1][0], results[selected - 1][1])
                        print 'Selected ', self.btmgr.selected_device, 'to monitor'
                except Exception:
                    print 'invalid selection \'', cmd, '\''
                #end if selected
            #end if selected_devices
        #end while True
        self.btmgr.done = True

def run():
    btmgr = BluetoothManager()
    btmgr.start()
    console = Console(btmgr)
    console.run()

run()
