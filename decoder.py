with open('data.txt', 'r') as file:
        data = file.read()
data = bytes.fromhex(data)

class Decoder:
    def __init__(self, data):
        self.data = data
    
    def get_cat(self):
        return self.data[0]
    
    def get_length(self):
        return int.from_bytes(self.data[1:3])
    
    def get_data_block(self):
        return self.data[3:]
    
    def get_fspecs(self):
        data_block = self.get_data_block()
        fspec = []
        for byte in data_block:
            if (byte & 1) == 1:
                fspec.append(byte)
            else:
                break
        return fspec
    
    def get_frns(self):
        fspecs = self.get_fspecs()
        bits = []
        for fspec in fspecs: 
            for i, c in enumerate(bin(fspec)[:1:-1], 1):
                if c == '1':
                    bits.append(i)
        return bits
    
    def decode(self):
        return None
        

    # def hex_to_bytes(self, hex_data):
    #     return bytes.fromhex(hex_data)
    
    # def byte_to_bits(self, byte):
    #     return bin(byte)[2:].zfill(8)

decoder = Decoder(data)
cat = decoder.get_cat()
length = decoder.get_length()
raw_data = decoder.get_data_block()
print(cat)
print(length)
print(len(raw_data) + 3)
fspecs = decoder.get_fspecs()
print(fspecs)
for fspec in fspecs:
    print(bin(fspec))
frns = decoder.get_frns()
print(frns)
         

