import os
import time
from multiprocessing import Process

processes = [Process(target=os.system, args=('python start_client.py -r > /dev/null 2>&1',)) for _ in range(3)]
game_owner = Process(target=os.system, args=('python start_client.py',))

game_owner.start()
time.sleep(0.05)

for p in processes:
    p.start()

game_owner.join()
for p in processes:
    p.join()
