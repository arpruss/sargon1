GRAPHICS = True # uses cv2 to display board

import z80 # pip3 --install z80, but modified to make af visible
import binascii
import time

if GRAPHICS:
    import cv2
    import numpy as np
    from hp1345_font_data import hp1345_font_data
    zoom = 6
    WINDOW = "Sargon"
    JUPITER_SCREEN = 0xC000
    MINIMUM_COMPUTE_TIME_PER_FRAME = 1. / 5
    JUPITER_WIDTH = 64
    JUPITER_LEFT_SIDE = 16
    JUPITER_HEIGHT = 32
    FLOODFILL = True
    cursorX = 0
    cursorY = 0
    
    keyfeed = ''
    moveFrom = True
    
    def mouseClick(event,x,y,flags,param):
        global keyfeed,moveFrom
        if event == cv2.EVENT_LBUTTONDOWN:
            left = (JUPITER_WIDTH*2-12*8)*zoom
            if x >= left:
                col = (x - left) // (zoom*12)
                row = 7 - y // (zoom*12)
                if 0 <= col <= 7 and 0 <= row <= 7:
                    keyfeed += chr(col+ord('a')) + chr(row+ord('1'))
                    if moveFrom:
                        keyfeed += '-'
                    moveFrom = not moveFrom
                
    cv2.namedWindow(WINDOW)
    cv2.setMouseCallback(WINDOW,mouseClick)

    def getch():
        global keyfeed
        while True:
            if keyfeed:
                c = keyfeed[0]
                keyfeed = keyfeed[1:]
                return c
            c = cv2.waitKey(1)
            if c >= 0:
                return chr(c)
        
    charset = []
    
    for i in range(256):
        data = np.zeros((3*zoom,2*zoom),dtype=np.uint8)
        data.fill(255)
        if i != ord('_'):
            v = hp1345_font_data[i]
        else:
            v = [ [(-18,-6),(36,0)], [(0,0)] ]
        def scale(p):
            return ( int(2*zoom*((p[0]-6)/18.)+zoom), int(3*zoom + zoom*((-(p[1]+7))/18.*2)-1) )
        if len(v):
            pos = (0,0)
            for stroke in v:
                for j in range(0,len(stroke)):
                    pos1 = (pos[0]+stroke[j][0],pos[1]+stroke[j][1])
                    if j != 0: 
                        cv2.line(data, scale(pos), scale(pos1), 0, 1)
                    pos = pos1
        charset.append(data)
    
    blocks = []
    
    for block in range(64):
        data = np.zeros((3,2),dtype=np.uint8)
        a = 1
        for j in range(3):
            for i in range(2):
                data[j,i] = 0 if (block & a) else 255
                a <<= 1
        blocks.append(data) # cv2.resize(data, (2*zoom,3*zoom), interpolation = cv2.INTER_NEAREST)
else:
    from getch import getch # pip3 --install py-getch

FILE = "zout/sargon-z80.hex"
ORG = 0x0000
START = ORG+0x1a00 
BLINKER = ORG+0x204C

def hexToMemory(filename,startAddress=0,length=-1,fill=0):
    memory = [None] * 0x10000
    last = 0
    with open(filename,"r") as f:
        for line in f:
            line = line.strip()
            if line[0] == ':':
                data = binascii.unhexlify(line[1:])
                if data[3] == 1:
                    break
                elif data[3] == 0:
                    count = data[0]
                    address = (data[1] << 8) | data[2]
                    for i in range(count):
                        a = address+i-startAddress
                        if memory[a] is not None:
                            print("Overlap at %04x" % a)
                            #raise Exception("overlap")
                        memory[a] = data[4+i]
                    last = max(last, a+1)
    for i in range(0x10000):
        if memory[i] is None:
            memory[i] = fill
    if length < 0:
        return bytes(memory[:last])
    else:
        return bytes(memory)

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
    if GRAPHICS:
        global cursorX, cursorY
        if c == ord('\n'):
            cursorY += 1
            cursorX = 0
        else:
            z.memory[JUPITER_SCREEN+cursorY*JUPITER_WIDTH+cursorX] = c
            cursorX += 1
    else:
        if c == ord('\n'):
            print(flush=True)
        else:
            print(chr(c),end='',flush=True)

def clearScreen():            
    if GRAPHICS:
        global cursorX, cursorY
        cursorX = 0
        cursorY = 0
        for i in range(JUPITER_WIDTH*JUPITER_HEIGHT):
            z.memory[JUPITER_SCREEN+i] = 0
    else:
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
        z.af = (z.af & 0xFF) | (ord(getch()) << 8)
    elif function1 == 0x81 and function2 == 0x1A:
        putCharacter(z.af>>8)
    elif function1 == 0x1F:
        print("[done]")
        return True
    else:
        print("Unknown function 0x%02x from 0x%04x" % (function1,addr-4))
        
    z.sp += 2
    z.pc = addr
    return False

z = z80.Z80Machine()
z.set_memory_block(0, hexToMemory(FILE))
z.set_breakpoint(0x38)
z.set_breakpoint(0x00)
if GRAPHICS: z.set_breakpoint(BLINKER) # blinker
z.pc = START

def getImage():
    screen = np.full((JUPITER_HEIGHT*3*zoom,JUPITER_WIDTH*2*zoom),255,dtype=np.uint8)
    right = np.full((JUPITER_HEIGHT*3,(JUPITER_WIDTH-JUPITER_LEFT_SIDE)*2),255,dtype=np.uint8)
    
    haveBlocks = False
    for x in range(JUPITER_LEFT_SIDE,JUPITER_WIDTH):
        for y in range(JUPITER_HEIGHT):
            c = z.memory[JUPITER_SCREEN + y * JUPITER_WIDTH + x]
            if 0x80 <= c < 0x80 + 64:
                x1 = (x-JUPITER_LEFT_SIDE)*2
                y1 = y*3
                right[y1:y1+3, x1:x1+2] = blocks[c-0x80]
                haveBlocks = True

    if FLOODFILL and haveBlocks:
        for col in range(8):
            for row in range(8):
                chunk = right[12*row:12*(row+1), 12*col:12*(col+1)]
                cv2.floodFill(chunk,None,(0,0),64 if (col+row) % 2 == 1 else 200)
                right[12*row:12*(row+1), 12*col:12*(col+1)] = chunk
            
    screen[0:JUPITER_HEIGHT*3*zoom,JUPITER_LEFT_SIDE*2*zoom:JUPITER_WIDTH*2*zoom] = cv2.resize(right, (2*zoom*(JUPITER_WIDTH-JUPITER_LEFT_SIDE),3*zoom*JUPITER_HEIGHT), interpolation = cv2.INTER_NEAREST)
        
    for x in range(JUPITER_WIDTH):
        for y in range(JUPITER_HEIGHT):
            c = z.memory[JUPITER_SCREEN + y * JUPITER_WIDTH + x]
            if c < 0x80:
                x1 = x*2*zoom
                y1 = y*3*zoom
                screen[y1:y1+3*zoom, x1:x1+2*zoom] = charset[c]

    return screen

def handleBreakpoints():
    if z.pc == 0x00:
        print("[reset]")
        return true
    elif z.pc == 0x38:
        return handle38()
    elif GRAPHICS and z.pc == BLINKER:
        time.sleep(0.01)
    else:
        return False    

if GRAPHICS:
    lastFrame = 0
    while True:
        z.ticks_to_stop = 200000
        events = z.run()
        if (events & z._BREAKPOINT_HIT) or time.time() >= lastFrame + MINIMUM_COMPUTE_TIME_PER_FRAME:
            t = time.time()
            image = getImage()
            cv2.imshow(WINDOW, image)
            if handleBreakpoints():
                break
            cv2.waitKey(1)
            lastFrame = time.time()
else:
    while True:
        events = z.run()
        if handleBreakpoints():
            break
    