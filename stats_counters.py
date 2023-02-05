import logging
if __name__=="__main__":
    logging.basicConfig(level=logging.DEBUG)

from dataclasses import dataclass


class Counter:
    def __init__(self):
        self.count:int=0

    def inc(self):
        self.count+=1

    def finish(self,total):
        self.percentage=self.count/total*100




class CounterSet:
    def __init__(self,counter_names:list[str]):
        self.counters:dict={name:Counter() for name in counter_names}
        self.total:int=0

    def inc(self,counter_name:str):
        self.total+=1
        self.counters[counter_name].inc()

    def finish_all(self):
        for  count in self.counters.values():
            count.finish(self.total)
    
    def __str__(self)->str:
        self.finish_all()
        bits:list[str]=[]
        name_length_padded=max(max([len(counter_name) for counter_name in self.counters.keys()])+3,8)
        for counter_name,counter in self.counters.items():
            bits.append(f'{counter_name:<{name_length_padded}}{counter.count:>6}    {counter.percentage:4.2f} %')
        
        bits.append(f'{"Total":<{name_length_padded}}{self.total:>6}    {100.0:4.2f} %')

        return "\n".join(bits)



if __name__=="__main__":
    import random
    test_sets=["armadillo","duck","parrots-living","parrots-deceased"]
    counts=CounterSet(test_sets)
    for i in range(1000):
        category=random.choice(test_sets)
        counts.inc(category)

    print(counts)


