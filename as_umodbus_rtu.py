#micropython basic modbus RTU (on top of RS485)
#send and receive is done asynchroniously

#https://www.chauvin-arnoux-energy.com/sites/default/files/download/ca2150-m_modbus_fr_a5.pdf

import uasyncio as asyncio
from machine import UART
from array import array
from time import sleep
from sys import exit
import struct

#crc16 constants valide for modbus-RTU
PRESET = 0xFFFF
POLYNOMIAL = 0xA001 # bit reverse of 0x8005

#Precalculated table of 32bytes to speed up crc calculation
#https://github.com/orgs/micropython/discussions/12891
_tab=array('H', [0, 52225, 55297, 5120, 61441, 15360, 10240, 58369, 40961, 27648, 30720, 46081, 20480, 39937, 34817, 17408])
# _tab = array("H", (_init4bit(i, POLYNOMIAL) for i in range(16))) # Create the table, based on _init4bit(), POLYNOMIAL
# 
# def _init4bit(crc, poly):     # create a single entry to the CRC table
#     for j in range(4):
#         if crc & 0x01:
#             crc = (crc >> 1) ^ poly
#         else:
#             crc = crc >> 1
#     return crc

#Modbus-RTU
#functions codes PDU
#just a subset, can be extended as needed
READ_HOLDING_REGISTER = 0x03
READ_INPUT_REGISTER = 0x04
WRITE_SINGLE_REGISTER = 0x06
WRITE_MODBUS_ADDRESS = 0x0002 #range is 0x0001~0x00F7

#ADU - PZEM004 specific
CALIBRATION = 0x41 #only address supported 0xF8, password 0x3721
RESET_ENERGY = 0x42

#Server=Master
class Server:
    def __init__(self, uart, crc_check=False):
        self.uart=uart
        self.clients=[None]*32
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.sreader = asyncio.StreamReader(self.uart)
        self.crc_check = crc_check #set to True if you want crc check on response
        
    def add_client(self,client):
        self.clients[client.address]=client
        
        
    async def sender(self,request):
        print(f"send: {request}")
        self.swriter.write(request)
        await self.swriter.drain()

    async def receiver(self):
        res = await self.sreader.read(40)
        #print(f'Received: {res}')
        
        if self.crc_check == True:
            if int.to_bytes(crc16(PRESET, res,len(res),_tab),2,'little') == b'\x00\x00':
                #print("crc_check: ok")
                address=res[0]
                client=self.clients[address]
                client.data=res[1:-2]#update client property remove first byte (adress) and two last bytes (crc) 
                client.data_decode() #decode message (specific to modbus device)
            else:
                print("crc_check: error")
        else:
            address=res[0]
            client=self.clients[address]
            client.data=res[1:-2]#update client property remove first byte (adress) and two last bytes (crc) 
            client.data_decode() #decode message (specific to modbus device)
            
    async def run(self,delay):
        while True:
            for client in self.clients:
                if client != None:
                    asyncio.create_task(self.sender(client.request))
                    await asyncio.sleep(delay)
                    asyncio.create_task(self.receiver())
            await asyncio.sleep(delay)

    def scan(self,max_add=36):
        print("search for clients on modbus...")
        slaves=[]
        for address in range(0,max_add):
            response=self.check_address(address)
            if response!=None:
                slaves.append(response)
        
        print(f"Found clients at address: {slaves}")
        return slaves


    def check_address(self,address):
        request=int.to_bytes(address,1,'big')
        request+=int.to_bytes(READ_HOLDING_REGISTER,1,'big')
        request+=b'\x00\x02\x00\x01'
        request+=int.to_bytes(crc16(PRESET, request,len(request),_tab),2,'little')
        print(request)
        self.uart.write(request)

        sleep(0.1)

        response=self.uart.read(40)
        if response==None:
            return None
        if response[4:5]==int.to_bytes(address,1,'big'):
            return address


    #not tested
    def setClientAddress(self, client, new_address):
        
        new_address=int.to_bytes(new_address,1,'big')
        
        if client.address==new_address:
            print(f'address already set to {self.address}')
            return    
        
        request=client.address
        request+=int.to_bytes(WRITE_SINGLE_REGISTER,1,'big')
        request+=int.to_bytes(WRITE_MODBUS_ADDRESS,2,'big')
        request+=b'\x00'
        request+=new_address
        request += int.to_bytes(crc16(PRESET, request,len(request),_tab),2,'little')
        
        self.uart.write(request)

        sleep(0.1)

        response=self.uart.read(40)
        
        if response[1:2]==b'\x86':
            raise Exception('Error setting address')
        else:
            self.address=new_address


class Client:
    def __init__(self,address,request):
        self.address=address
        #request is calculed once at object creation to avoid overhead and allow highest sampling rate
        self.request=int.to_bytes(address,1,'big')
        self.request+=request
        self.request+=int.to_bytes(crc16(PRESET, self.request,len(self.request),_tab),2,'little')
        print(f"request: {self.request}")
        self.data=None
        
    #overload this method to suit your specific case and modbus device
    def data_decode(self):
        #TODO: decode data
        print(f"{self.address} : {self.data}")
        

# 71µs per byte
# def crc16(data):
#     crc = PRESET
#     for c in data:
#         crc = crc ^ c
#         for j in range(8):
#             if (crc & 1) == 0:
#                 crc = crc >> 1
#             else:
#                 crc = crc >> 1
#                 crc = crc ^ POLYNOMIAL
#     return struct.pack('<H',crc)

# crc16 viper 4bit table implementation from https://github.com/rkompass and https://github.com/robert-hh
# https://github.com/orgs/micropython/discussions/12891
# 2.16µs per byte
@micropython.viper
def crc16(crc: int, data: ptr8, n: int, tab: ptr16) -> int:
    i: int  = 0
    while i < n:
        d = data[i]
        crc = (crc >> 4) ^ tab[(crc ^ d) & 0x0f]
        crc = (crc >> 4) ^ tab[(crc ^ (d >> 4)) & 0x0f]
        i += 1
    return crc



#Boilerplate code from petterhinch async tutorial
#https://github.com/peterhinch/micropython-async/blob/master/v3/docs/TUTORIAL.md#511-global-exception-handler
def set_global_exception():
    def handle_exception(loop, context):
        import sys
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

async def toto(): #never ending asyncio coro
    while True:
        print("toto")
        await asyncio.sleep(4)

async def main():
    set_global_exception()  # Debug aid
    
    uart = UART(2, 9600, bits=8, parity=None, stop=1, timeout=0, tx=16, rx=17)
    
    modbus_server = Server(uart,crc_check=True)
    
    modbus_server.scan(4)
    
    request=int.to_bytes(READ_INPUT_REGISTER,1,'big')
    request+=b'\x00\x00\x00\x0A'

    
    client_1 = Client(1,request)
    modbus_server.add_client(client_1)

    client_2 = Client(2,request)
    modbus_server.add_client(client_2)
    
    asyncio.create_task(toto()) #add another asyncio task here
    
    await modbus_server.run(delay=1)
    

if __name__=="__main__":
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop() # Clear retained state

