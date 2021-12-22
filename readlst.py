def getSymbols(file):
    scanning = False
    list = {}
    
    with open(file) as f:
        for line in f:
            line = line.strip()
            if not scanning and line == "Symbol Table":
                scanning = True
            else:
                tokens = line.split()
                if len(tokens) == 3:
                    try:
                        list[tokens[0]] = int(tokens[2])
                    except:
                        pass

    return list