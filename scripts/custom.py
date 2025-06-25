# -- custom.py script
def custom(base, gen, io, args):
    for event in io.rx():
        # if event[3] ==
        if event[3][:1] == b'\x3e':
            io.tx(event)
            break