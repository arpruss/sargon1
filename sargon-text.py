import z80 # pip3 install z80, but modified to make af visible
import binascii
import time
import sys
import readhex
from getch import getch # pip3 install py-getch

FILE = "zout/sargon-z80.hex"
ORG = 0x0000
START = ORG+0x1a00 
BLINKER = ORG+0x204C

def getWord(address):
    return z.memory[address] | (z.memory[(address+1) & 0xFFFF] << 8)

def setWord(address,data):
    z.memory[address] = data & 0xFF
    z.memory[(address+1) & 0xFFFF] = data >> 8
    
def getBytes(address,count):
    data = bytearray(count)
    for i in range(count):
        data[i] = z.memory[(address+i)&0xFFFF]
    return data
    
def putCharacter(c):
    if c == ord('\n'):
        print(flush=True)
    else:
        print(chr(c),end='',flush=True)

def clearScreen():            
    print(flush=True)
        
def handle38():
    addr = getWord(z.sp)
    function1 = z.memory[addr]
    addr = (addr+1) & 0xFFFF
    function2 = z.memory[addr]
    addr = (addr+1) & 0xFFFF
    if (function1 == 0xb2 or function1 == 0xb3) and function2 == 0x1a:
        msg = getWord(addr)
        addr = (addr+2) & 0xFFFF
        length = getWord(addr)
        addr = (addr+2) & 0xFFFF
        pos = msg
        while length:
            c = z.memory[pos]
            if c == ord('['):
                c = z.memory[pos+1]
                pos += 2
                if c == 0x1c:
                    clearScreen()
                elif c == 0x83:
                    putCharacter(ord('-'))
            else:
                putCharacter(c)
            pos += 1
            length -= 1
        if function1 != 0xb3:
            putCharacter(ord('\n'))
    elif function1 == 0x92 and function2 == 0x1a:
        addr = (addr+2) & 0xFFFF
        putCharacter(ord('\n'))
    elif function1 == 0x81 and function2 == 0x00:
        c = getch()
        z._StateBase__af[1] = ord(c)
        
    elif function1 == 0x81 and function2 == 0x1A:
        putCharacter(z._StateBase__af[1])
    elif function1 == 0x1F:
        print("[done]")
        return True
    else:
        print("Unknown function 0x%02x from 0x%04x" % (function1,addr-4))
        
    z.sp += 2
    z.pc = addr
    return False

z = z80.Z80Machine()
z.set_memory_block(0, readhex.hexToMemory(FILE))
z.set_breakpoint(0x38)
z.set_breakpoint(0x00)
z.pc = START

def handleBreakpoints():
    if z.pc == 0x00:
        print("[reset]")
        return true
    elif z.pc == 0x38:
        return handle38()
    else:
        return False    

while True:
    events = z.run()
    if handleBreakpoints():
        break
    