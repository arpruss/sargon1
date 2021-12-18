import binascii

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

