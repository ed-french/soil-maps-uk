import logging
if __name__=="__main__":
    logging.basicConfig(level=logging.DEBUG)

from PIL import Image,ImageDraw,ImageFont

from typing import ClassVar
from dataclasses import dataclass
import numpy as np

import json

from stats_counters import CounterSet




colors={"OK BOTH":(50,255,50,255),
        "LOW K ONLY":(130,80,0,255),
        "LOW P ONLY":(0,120,100,255),
        "LOW BOTH":(255,0,0,255)}



@dataclass
class MaterialMap:
    material_code:str|None=None
    dataset:np.ndarray|None=None
    ncols:int|None=None
    nrows:int|None=None
    xllcorner:float|None=None
    yllcorner:float|None=None
    cellsize:float|None=None
    NODATA_value:float|None=None
    max_value:float|None=None
    min_value:float|None=None
    param_names:ClassVar[list[str]]=["ncols" ,"nrows","xllcorner","yllcorner","cellsize","NODATA_value"]
    image:Image.Image|None=None

    @classmethod
    def from_source_file(cls,material_code:str):
        with open(f"NSI_GRIDS/{material_code}_grid.txt","r") as infile:
            # Grab the parameters
            
            paramvals={}
            for _ in cls.param_names:
                paramline=infile.readline()
                bits=paramline.split(" ")
                pnamefound=bits[0]
                pvaluefound=float(bits[-1])
                if pnamefound not in cls.param_names:
                    logging.error(f"Unexpected parameter in the file: {pnamefound}")
                else:
                    paramvals[pnamefound]=pvaluefound
            
            # Check we found them all
            for param in cls.param_names:
                if param not in paramvals:
                    raise KeyError(f"Could not find parameter : {param} in the file for {material_code}")
 
        

            # Now load all the data
            width=int(paramvals["ncols"])
            height=int(paramvals["nrows"])
            logging.info(f"Creating array ({width},{height})")
            dataset=np.empty(shape=(width,height),dtype=np.single)
            print(dataset.shape)
            min_value=99999999999999999999
            max_value=-99999999999999999999
            for row in range(int(paramvals["nrows"])):
                inline=infile.readline()
                for col,pointstr in enumerate(inline.strip().split(" ")):
                    try:
                        pointval=float(pointstr)
                    except ValueError as e:
                        #logging.debug(f"Skipping: '{pointstr}'")
                        pass
                    else:
                        if pointval>paramvals["NODATA_value"]:
                            if pointval<min_value:
                                min_value=pointval
                            if pointval>max_value:
                                max_value=pointval
                        dataset[col,row]=pointval


            paramvals["max_value"]=max_value
            paramvals["min_value"]=min_value

           
            res=cls(material_code,dataset,**paramvals)
            return res
    
    def to_JSON(self)->str:
        res=['{']
        res.append(f'\t"mineral":"{self.material_code}",')
        for param in self.param_names+["max_value","min_value"]:
            res.append(f'\t"{param}":{self.__getattribute__(param)},')
        
        res.append('"dataset":')

        rounded=np.around(self.dataset,3)

        res.append(json.dumps(rounded.tolist()))
        

        res.append("}")
        return "\n".join(res)

    @classmethod
    def from_json_file(cls,mineral_code:str):
        res=cls()
        res.material_code=mineral_code
        filename=mineral_code+"_map.json"
        with open(filename) as infile:
            json_version=json.load(infile)
        for param in res.param_names+["max_value","min_value"]:
            setattr(res,param,json_version[param])

        dataset=json_version['dataset']
        res.dataset=np.array(dataset,dtype=np.single)

        return res

        


    def save_json(self):
        filename=self.material_code+"_map.json"
        with open(filename,"w") as outfile:
            outfile.write(self.to_JSON())



    def __str__(self):
        bits:list[str]=[]
        for arg in self.param_names:
            bits.append(f'{arg}\t:\t{self.__getattribute__(arg)}')

        return "\n".join(bits)


    def get_image(self,floor)->Image.Image:
        img=Image.new(mode="RGBA",size=(int(self.ncols)+0,int(self.nrows)+0),color=(0,0,0,1))
        
        for row in range(int(self.nrows)):
            for col in range(int(self.ncols)):
                value=self.dataset[col,row]
                if value!=self.NODATA_value:
                    prop=min(int(700*(value-self.min_value)/(self.max_value-self.min_value)),255)
                    if value<floor:
                        color=(100,prop,prop,255)
                    else:
                        color=(0,prop,prop,255)
                    img.putpixel((col,row),color)
        self.image=img
        return img

    def calc_distribution_get_tenpercentile(self,percentile=10)->float:
        # Compute frequency and bins
        frequency, bins = np.histogram(self.dataset, bins=50, range=[self.min_value, self.max_value])

        # Pretty Print
        for b, f in zip(bins[1:], frequency):
            print(round(b, 3),f, ' '.join(np.repeat('*', f//300)))

        # Find 10 percentile
        
        count_land=0
        for row in range(int(self.nrows)):
            for col in range(int(self.ncols)):
                if self.dataset[col,row]>self.NODATA_value:
                    count_land+=1
        
        # calc 10% of this:
        tenpercent=int(count_land*percentile/100)

        acc=0
        for b,f in zip(bins[2:],frequency[1:]):
            acc+=f
            if acc>tenpercent:
                return b

    def show(self):
        self.get_image(0).show()




class MapSets:
    """
            Holds the land use map and
            the mineral maps
    
    
    """


    @classmethod
    def from_source_files(cls,material_list:list[str]):
        res=cls()
        res.mineral_maps:dict[str,MaterialMap]={}

        for material in material_list:

            map=MaterialMap.from_source_file(material)
            res.mineral_maps[material]=map

        res.get_land_use_map()

        return res

    @classmethod
    def from_json_files(cls,material_list:list[str]):
        res=cls()
        res.mineral_maps:dict[str,MaterialMap]={}

        for material in material_list:

            map=MaterialMap.from_json_file(material)
            res.mineral_maps[material]=map

        res.get_land_use_map()
        return res


    def get_master_map(self,min_k=0.6,min_p=0.06)->Image.Image:
        """
                returns a composite image
                where red is arable which needs mineral supplementation
                and white is OK without mineral supplementation
       
        """
        print(f'K tenpercentile= {self.mineral_maps["K"].calc_distribution_get_tenpercentile()}')
        print(f'P tenpercentile= {self.mineral_maps["P"].calc_distribution_get_tenpercentile()}')
        img=Image.new(mode="RGBA",size=(515,640),color=(0,0,0,0))
        k_nodata=self.mineral_maps["K"].NODATA_value
        p_nodata=self.mineral_maps["P"].NODATA_value

        counters=CounterSet(["OK BOTH","LOW K ONLY","LOW P ONLY","LOW BOTH"])

        for row in range(640):
            print()
            for col in range(515):
                k=self.mineral_maps["K"].dataset[col,row]
                if k==k_nodata:
                    color=(0,0,0,0) # transparentblack it's the sea!
                else:
                    # Not sea, but could be not arable
                    arable=self.arable_map[row,col]
                    
                    if arable<50:
                        color=(0,7,0,255) # Dark green
                    else:
                        # We are arable, but maybe good or bad!
                        p=self.mineral_maps["P"].dataset[col,row]

                        p_ok=(p>min_p)
                        k_ok=(k>min_k)

                        if p_ok and k_ok:
                            print(".",end="")
                            color=colors["OK BOTH"]# Bright green
                            counters.inc("OK BOTH")

                        else:
                            if not p_ok and not k_ok:
                                print("X",end="")
                                color=colors["LOW BOTH"] # Bright red
                                counters.inc("LOW BOTH")

                            else:
                                if p_ok:
                                    print("K",end="") 
                                    color=colors["LOW K ONLY"]# Orangey/brown=low K
                                    counters.inc("LOW K ONLY")

                                else:
                                    print("P",end="")
                                    color=colors["LOW P ONLY"]# bluey-green  
                                    counters.inc("LOW P ONLY")                      


                img.putpixel((col,row),color)




        print(counters)

        
        title_fnt = ImageFont.truetype(r"C:\Windows\Fonts\Tahoma.ttf", 24)
        
        # get a drawing context
        d = ImageDraw.Draw(img)

        # draw multiline text
        d.multiline_text((370, 10), "Arable\nMineral\nSufficiency", font=title_fnt, fill=(0, 255, 255),align='right')

        table=str(counters)


        key_font=ImageFont.truetype("FreeMono.ttf",size=9)#r"C:\Windows\Fonts\MTEXTRA.TTF"
        d.multiline_text((10,100-75), table, font=key_font, fill=(200,200,200))

        for i,(cat,color) in enumerate(colors.items()):
            d.rectangle((110,101+12*i-75,120,109+12*i-75),fill=color)


                

        return img
                

                 
                    








    def get_land_use_map(self):

        raw_pixels=np.array(Image.open('land_use_aligned_cropped.png'))
        w,h,_=raw_pixels.shape
                
        arable=np.empty(shape=(w,h),dtype=np.uint8)

        # Loop through the pixels
        for y in range(len(raw_pixels)):
            for x in range(len(raw_pixels[0])):
                try:
                    pixel=raw_pixels[y,x]
                    land_type=self.pixel_class(pixel)
                    new_pixel=self.arable_pixel_enhance(pixel,land_type)
                    arable[y,x]=235*(land_type==1)+20
                    raw_pixels[y,x]=new_pixel
                except IndexError:
                    logging.debug(f'Skipping pixel {(x,y)}')

        self.arable_map=arable


    def get_arable_map_img(self)->Image.Image:
        arable_img=Image.fromarray(self.arable_map)
        return arable_img



    @staticmethod
    def pixel_class(pixel):
        """
            Returns -1 for sea
            Returns 0 for land non-arable
            Returns 1 for arable
        """
        r,g,b,a=pixel
        if a==0:
            return -1

        rr,gr,br,ar=129,207,56,255

        #arable pixels - return as is
        if (abs(r-rr)+abs(g-gr)+abs(b-br)+abs(a-ar))<20:
            return 1
        
        #return semitxp version
        return 0


    @staticmethod
    def arable_pixel_enhance(pixel,pixel_class):
        if pixel_class==-1:# Sea
            return pixel 
        if pixel_class==1: # Arable as bright white
            return (255,255,255,255)
        
        r,g,b,a=pixel
        return (r//4,g//4,b//4,255) # Other land goes darker

    
    def get_composite(self,mineral_code,floor_level=0.0)->Image.Image:
        mineral_image=self.mineral_maps[mineral_code].get_image(floor_level)
        canvas=Image.new(mode="RGBA",size=(515,640),color=(0,0,0,0))
        arable_img=self.get_arable_map_img()

        canvas.paste(mineral_image,(0,0),arable_img)
        return canvas





    


    def save_master_map(self):
        map=self.get_master_map()
        map.save("PK_Combined_map.png")

    








if __name__=="__main__":

    if True:
        ms=MapSets.from_source_files(["K","P"])

        ms.save_master_map()


