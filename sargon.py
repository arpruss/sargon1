import z80 # pip3 --install z80, but modified to make af visible
import binascii
import time
import sys
import cv2
import numpy as np
import hp1345
import readhex
import math

try:
    import inputs
    import threading
    
    eventList = []
    
    def monitorGamepad():
        while True:
            try:
                for e in inputs.get_gamepad():
                    eventList.append(e)
            except inputs.UnpluggedError:
                time.sleep(0.5)
    
    gamepadThread = threading.Thread(target=monitorGamepad)
    gamepadThread.daemon = True
    gamepadThread.start()
    
    def gamepadEvents():
        copy = eventList[:]
        eventList.clear()
        return copy
        
    def haveGamepad():
        return len(inputs.devices.gamepads)>0
        
except ImportError:
    def gamepadEvents(): return []
    def haveGamepad(): return False

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

OPTIONS = {
    STATE_ASK_PLAY: (ord('y'),ord('n')),
    STATE_ASK_COLOR: (ord('w'),ord('b')),
    STATE_ASK_LEVEL: (ord('1'),ord('2'),ord('3'),ord('4'),ord('5'),ord('6')),
    STATE_ASK_ANALYZE: (ord('y'),ord('n'))
}

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

boardCursorX = None
boardCursorY = None

keyfeed = ''
moveFrom = True

def makeMove(col,row):
    global keyfeed,moveFrom
    keyfeed += chr(col+ord('a')) + chr(row+ord('1'))
    if moveFrom:
        keyfeed += '-'
    moveFrom = not moveFrom

def mouseClick(event,x,y,flags,param):
    if event == cv2.EVENT_LBUTTONDOWN:
        left = (JUPITER_WIDTH*2-12*8)*ZOOM
        if x >= left:
            col = (x - left) // SQUARE
            row = 7 - y // SQUARE
            if 0 <= col <= 7 and 0 <= row <= 7:
                mameMove(col,row)
            
cv2.namedWindow(WINDOW)
cv2.setMouseCallback(WINDOW,mouseClick)

def updateScreen():
    cv2.imshow(WINDOW, getImage())

def getch():
    global keyfeed, boardCursorX, boardCursorY
    
    if state in OPTIONS and haveGamepad():
        putCharacter(OPTIONS[state][0], advance=False)
        updateScreen()
    
    while True:
        if keyfeed:
            c = keyfeed[0]
            keyfeed = keyfeed[1:]
            return c
        c = cv2.waitKey(1)
        if cv2.getWindowProperty(WINDOW, 0) == -1:
            sys.exit(0)
        if c == 27 and state != STATE_SETUP:
            if state in OPTIONS and ord('n') in OPTIONS[state]:
                return 'n'
            c = 18
        if (c == 10 or c == 13) and state in OPTIONS and ord('n') in OPTIONS[state]:
            pressed = getCharacter() 
            if pressed in OPTIONS[state]:
                return chr(pressed)
            else:
                return 'y'
        if c >= 0:
            return chr(c)
        
        events = gamepadEvents()
        if events:
            for e in events:
                if state == STATE_PLAY:
                    if boardCursorX == None:
                        boardCursorX = 3
                        boardCursorY = 3
                    if e.code == 'ABS_HAT0X':
                        if e.state < 0:
                            boardCursorX -= 1
                            updateScreen()
                        elif e.state > 0:
                            boardCursorX += 1
                            updateScreen()
                    elif e.code == 'ABS_HAT0Y':
                        if e.state < 0:
                            boardCursorY -= 1
                            updateScreen()
                        elif e.state > 0:
                            boardCursorY += 1
                            updateScreen()
                    elif e.code == 'BTN_EAST' and e.state:
                        makeMove(boardCursorX, 7-boardCursorY)
                    elif e.code == 'BTN_START' and e.state:
                        return chr(18)
                elif state in OPTIONS:
                    options = OPTIONS[state]
                    if e.code == 'ABS_HAT0X' and e.state != 0:
                        current = getCharacter()
                        try:
                            index = options.index(current)
                            if e.state < 0:
                                index = (len(options)+index-1) % len(options)
                            else:
                                index = (index+1) % len(options)
                        except:
                            index = 0
                        putCharacter(options[index], advance=False)
                        updateScreen()
                    elif e.code == 'BTN_EAST' and e.state:
                        current = getCharacter()
                        if current in options:
                            return chr(current)
                    elif e.code == 'BTN_SOUTH' and e.state and ord('n') in options:
                        return 'n'
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
    
def putCharacter(c, advance=True):
    global cursorX, cursorY
    if c == ord('\n'):
        if advance:
            cursorY += 1
            cursorX = 0
    else:
        z.memory[JUPITER_SCREEN+cursorY*JUPITER_WIDTH+cursorX] = c
        if advance:
            cursorX += 1
            
def getCharacter():
    return z.memory[JUPITER_SCREEN+cursorY*JUPITER_WIDTH+cursorX]

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
                cv2.floodFill(chunk,None,(0,0),64 if chunk[0,0] == 0 else 192)
                right[12*row:12*(row+1), 12*col:12*(col+1)] = chunk
            
    screen[0:JUPITER_HEIGHT*VCHAR,JUPITER_LEFT_SIDE*HCHAR:JUPITER_WIDTH*HCHAR] = cv2.resize(right, (HCHAR*(JUPITER_WIDTH-JUPITER_LEFT_SIDE),VCHAR*JUPITER_HEIGHT), interpolation = cv2.INTER_NEAREST)
        
    for x in range(JUPITER_WIDTH):
        for y in range(JUPITER_HEIGHT):
            c = z.memory[JUPITER_SCREEN + y * JUPITER_WIDTH + x]
            if c < 0x80:
                x1 = x*HCHAR
                y1 = y*VCHAR
                screen[y1:y1+VCHAR, x1:x1+HCHAR] = charset[c]
                
    if state == STATE_PLAY and boardCursorX is not None and boardCursorY is not None:
        x = boardCursorX * SQUARE + JUPITER_LEFT_SIDE*HCHAR + SQUARE // 2
        y = boardCursorY * SQUARE + SQUARE // 2
        cv2.circle(screen, (x,y), int(SQUARE * 0.45), 0 if (boardCursorX+boardCursorY)%2 == 0 else 255, 2, cv2.LINE_AA)

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
        updateScreen()
        if handleBreakpoints():
            break
        cv2.waitKey(1)
        if cv2.getWindowProperty(WINDOW, 0) == -1:
            break

        lastFrame = time.time()
