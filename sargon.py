import z80 # pip3 --install z80, but modified to make af visible
import binascii
import time
import sys
import cv2
import numpy as np
import hp1345
import readhex
import math

MINIMUM_COMPUTE_TIME_PER_FRAME = 1. / 5
ZOOM = 6
FLOODFILL = True
WINDOW = "Sargon"

STATE_ASK_PLAY = 0
STATE_ASK_COLOR = 1
STATE_ASK_LEVEL = 2
STATE_ASK_ANALYZE = 3
STATE_PLAY = 4
STATE_END_PLAY = 5
STATE_SETUP = 6

FILE = "zout/sargon-z80.hex"
ORG = 0x0000
START = ORG+0x1a00 
BLINKER = ORG+0x204C

state = STATE_ASK_PLAY

JUPITER_SCREEN = 0xC000
JUPITER_WIDTH = 64
JUPITER_LEFT_SIDE = 16
JUPITER_HEIGHT = 32
VCHAR = ZOOM*3
HCHAR = ZOOM*2
SQUARE = ZOOM*12

cursorX = 0
cursorY = 0

keyfeed = ''
moveFrom = True

def mouseClick(event,x,y,flags,param):
    global keyfeed,moveFrom
    if event == cv2.EVENT_LBUTTONDOWN:
        left = (JUPITER_WIDTH*2-12*8)*ZOOM
        if x >= left:
            col = (x - left) // SQUARE
            row = 7 - y // SQUARE
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
        if cv2.getWindowProperty(WINDOW, 0) == -1:
            sys.exit(0)
        if c >= 0:
            return chr(c)
    
charset = []

for i in range(256):
    data = np.zeros((VCHAR,HCHAR),dtype=np.uint8)
    data.fill(255)
    for start,end in hp1345.hp1345_render(chr(i), width=HCHAR, round=round, dotSize=0):
        cv2.line(data, start, end, 0, 1)
    charset.append(data)

blocks = []

for block in range(64):
    data = np.zeros((3,2),dtype=np.uint8)
    a = 1
    for j in range(3):
        for i in range(2):
            data[j,i] = 0 if (block & a) else 255
            a <<= 1
    blocks.append(data)

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
    global cursorX, cursorY
    if c == ord('\n'):
        cursorY += 1
        cursorX = 0
    else:
        z.memory[JUPITER_SCREEN+cursorY*JUPITER_WIDTH+cursorX] = c
        cursorX += 1

def clearScreen():            
    global cursorX, cursorY
    cursorX = 0
    cursorY = 0
    for i in range(JUPITER_WIDTH*JUPITER_HEIGHT):
        z.memory[JUPITER_SCREEN+i] = 0
        
def updateState(msg):
    global state
    s = msg.decode("ascii", "ignore")
    if 'CARE FOR' in s:
        state = STATE_ASK_PLAY
    elif 'LIKE TO ANALYZE' in s:
        state = STATE_ASK_ANALYZE
    elif 'DO YOU WANT TO PLAY' in s:
        state = STATE_ASK_COLOR
    elif 'LOOK AHEAD' in s:
        state = STATE_ASK_LEVEL
    elif 'SARGON' in s:
        state = STATE_PLAY
            
def handle38():
    global state
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
        updateState(getBytes(msg, length))
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
        if state == STATE_ASK_ANALYZE and c in ('y','Y'):
            state = STATE_SETUP
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
z.set_breakpoint(BLINKER) 
z.pc = START

def getImage():
    screen = np.full((JUPITER_HEIGHT*VCHAR,JUPITER_WIDTH*HCHAR),255,dtype=np.uint8)
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
                cv2.floodFill(chunk,None,(0,0),64 if chunk[0,0] == 0 else 200)
                right[12*row:12*(row+1), 12*col:12*(col+1)] = chunk
            
    screen[0:JUPITER_HEIGHT*VCHAR,JUPITER_LEFT_SIDE*HCHAR:JUPITER_WIDTH*HCHAR] = cv2.resize(right, (HCHAR*(JUPITER_WIDTH-JUPITER_LEFT_SIDE),VCHAR*JUPITER_HEIGHT), interpolation = cv2.INTER_NEAREST)
        
    for x in range(JUPITER_WIDTH):
        for y in range(JUPITER_HEIGHT):
            c = z.memory[JUPITER_SCREEN + y * JUPITER_WIDTH + x]
            if c < 0x80:
                x1 = x*HCHAR
                y1 = y*VCHAR
                screen[y1:y1+VCHAR, x1:x1+HCHAR] = charset[c]

    return screen

def handleBreakpoints():
    if z.pc == 0x00:
        print("[reset]")
        return true
    elif z.pc == 0x38:
        return handle38()
    elif z.pc == BLINKER:
        time.sleep(0.01)
    else:
        return False    

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
        if cv2.getWindowProperty(WINDOW, 0) == -1:
            break

        lastFrame = time.time()
