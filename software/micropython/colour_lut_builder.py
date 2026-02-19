#This was the Claude sonnet 4.5 builder for the LUT
def create_color_lut():
    lut = [] 
    for i in range(256):
        if i <= 170:
            progress = i / 170.0
            r = int(255 * progress)
            g = 0
            b = int(255 * (1 - progress))
        else:
            progress = (i - 171) / 84.0
            r = 255
            g = int(255 * progress)
            b = 0
        lut.append((r, g, b))
    return lut

#this is astrolabe's generalised LUT builder
#color_list must be same length as colour_stop_positions. positions must be ascending order. range top must be = top position
def generalised_color_lut(color_list, color_stop_positions, range_top_value, step_size):
    lut = []
    color_pairs = []
    stop_pairs = []
    
    for i in range(len(color_list)-1):
        color_pairs.append([color_list[i],color_list[i+1]])
        stop_pairs.append([color_stop_positions[i],color_stop_positions[i+1]])
#     print("colour_pairs",color_pairs)
#     print("stop_pairs",stop_pairs)
    
    start_val=0
    for index, pair in enumerate(color_pairs): 
#         progress=#0-1 value
#         print(index, pair)
        for i in range(start_val,range_top_value,step_size): #I have constructed this to work with 255 color values. For LUTS that step at 1 unit oer step, it looks algood.
            #for LUTS that step at greater steps, more thought is required when calling them: e.g., calling with step_size=256/4 will not perfectly map from start to end (the last colour step will be missing) Therefor, call with correspondingly coarser steps. (n-1)
            if i<=stop_pairs[index][1]:
                progress= (i-stop_pairs[index][0])/(stop_pairs[index][1]-stop_pairs[index][0]) #progress is a 0-1 parameterized value within each stop range
#                 print(progress)
                #base value + delta (can be +ve or -ve) * progress fraction of delta's application across range
                r=int(pair[0][0]+((pair[1][0]-pair[0][0])*progress))
                g=int(pair[0][1]+((pair[1][1]-pair[0][1])*progress))
                b=int(pair[0][2]+((pair[1][2]-pair[0][2])*progress))
#                 print(r,g,b)
                lut.append((r, g, b))
            else:
#                 print('next colour transition/stop range')
                start_val=i
                break #break out so the start_val isn't continuously updated as the loops runs out normally
        
#     print(lut)
    
    return lut