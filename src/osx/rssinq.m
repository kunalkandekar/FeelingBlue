#import <Foundation/Foundation.h> 
#import <Cocoa/Cocoa.h> 
#import <IOBluetooth/objc/IOBluetoothDeviceInquiry.h>
#import <IOBluetooth/objc/IOBluetoothDevice.h>
#import <IOBluetooth/objc/IOBluetoothHostController.h>
#import <IOBluetooth/IOBluetoothUtilities.h>

@interface RSSIFetcher: NSObject {}
-(void) readRSSIForDeviceComplete:(id)controller device:(IOBluetoothDevice*)device 
                             info:(BluetoothHCIRSSIInfo*)info error:(IOReturn)error; 

@end

@interface Discoverer: NSObject {}
@property (nonatomic, retain) NSMutableArray *devices;

-(void) deviceInquiryComplete: (IOBluetoothDeviceInquiry*) sender 
                            error: (IOReturn) error
                            aborted: (BOOL) aborted;
-(void) deviceInquiryDeviceFound: (IOBluetoothDeviceInquiry*) sender
                            device: (IOBluetoothDevice*) device;


- (void) getRSSI: (NSString*) addrStr;

- (void) discoverDevices;
@end

@implementation Discoverer
@synthesize devices;

- (id)init {
	self = [super init];
    self.devices = [[[NSMutableArray alloc] init] autorelease]; 
	return self;
}

-(void) deviceInquiryComplete: (IOBluetoothDeviceInquiry*) sender 
                            error: (IOReturn) error
                            aborted: (BOOL) aborted
{
    printf("inquiry complete. Found %u devices.\n", [devices count]);
    CFRunLoopStop( CFRunLoopGetCurrent() );
    int i = 0;  //too lazy to add c99 to make options 
	for (i = 0; i < [devices count]; i++) {
		IOBluetoothDevice *device = [devices objectAtIndex: i];
        [self getRSSI: [device getAddressString]];
	}
}

-(void) deviceInquiryDeviceFound: (IOBluetoothDeviceInquiry*) sender
                            device: (IOBluetoothDevice*) device
{
    //printf("discovered %s : %s\n", [[device getAddressString] cString], [[device getName] cString]);
    [devices addObject: [[device copy] autorelease]];
}

- (void) discoverDevices
{
    IOBluetoothDeviceInquiry *bdi =  [[IOBluetoothDeviceInquiry alloc] init];
    [bdi setDelegate: self];
    
    [bdi start];

    CFRunLoopRun();

    [bdi release];
}

- (void) getRSSI: (NSString*) addrStr
{
    NSAutoreleasePool *pool = [[NSAutoreleasePool alloc] init]; 
    NSLog(@"start"); 

    IOBluetoothHostController *hci = [IOBluetoothHostController defaultController];
    //NSString *addrStr = @"xx:xx:xx:xx:xx:xx";
    BluetoothDeviceAddress addr;
    IOBluetoothNSStringToDeviceAddress(addrStr, &addr);
    IOBluetoothDevice *device = [[IOBluetoothDevice alloc] init];
    device = [IOBluetoothDevice withAddress:&addr];
    [device retain];
    [device openConnection];
    RSSIFetcher *rssi = [[RSSIFetcher alloc] init];
    [hci setDelegate:rssi];
    [hci readRSSIForDevice:device];
    CFRunLoopRun();
    [hci release];
    [rssi release];
    [pool release];
} 
@end

@implementation RSSIFetcher
- (void) readRSSIForDeviceComplete:(id)controller device:(IOBluetoothDevice*)device 
                              info:(BluetoothHCIRSSIInfo*)info error:(IOReturn)error
{
    if (error != kIOReturnSuccess) {
        NSLog(@"readRSSIForDeviceComplete return error");
        CFRunLoopStop(CFRunLoopGetCurrent());
    }
    if (info->handle == kBluetoothConnectionHandleNone) {
        NSLog(@"readRSSIForDeviceComplete no handle");
        CFRunLoopStop(CFRunLoopGetCurrent());
    }
    //NSLog(@"RSSI = %i dBm ", info->RSSIValue);
    printf("device %s : %s rssi=%d\n", [[device getAddressString] cString], [[device getName] cString], info->RSSIValue);
    [NSThread sleepUntilDate: [NSDate dateWithTimeIntervalSinceNow: 5]];
    [device closeConnection];
    [device openConnection];
    [controller readRSSIForDevice:device];
}
@end


//build with: gcc -framework foundation -framework iobluetooth rssinq.m -o rssinq
int main (int argc, const char * argv[]) { 
    NSAutoreleasePool *pool = [[NSAutoreleasePool alloc] init]; 
    NSLog(@"start"); 

    Discoverer *d = [[Discoverer alloc] init];
    [d discoverDevices];
    [d release];
    [pool release];

    return 0; 
}
