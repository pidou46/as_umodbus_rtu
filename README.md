# as_umodbus_rtu
micropython async basic modbus rtu module

It's not modbus feature full, tested only with PZEM_004t energy counter device on esp32 with MP 1.20

By instancing mutiple Server you can create multiple modbus network on separate UART. Each modbus network can connect multiple clients theorically 247 but I limit it to 32 in the code

Thanks to asyncio, the communication is done asynchroniously, the CPU is not blocking waiting for client response so you can run other task concurently.

I tried to make the code efficient by precalculating the request crc and give the choice to check or not the crc of the response.


