# as_umodbus_rtu
micropython async basic modbus rtu module

It's not modbus feature full, tested only with 2 x PZEM_004t energy counter device on esp32 with MP 1.20, but contain no esp32 specific code so should run on any micropython device.

By instancing mutiple Server you can create multiple modbus network on separate UART. Each modbus network can connect multiple clients theorically 247 but I limit it to 32 in the code

Thanks to asyncio, the communication is done asynchroniously, the CPU is not blocking waiting for client response so you can run other task concurently.

I tried to make the code efficient by precalculating the crc request and give the choice to check or not the crc of the response at the server side.
Check https://github.com/orgs/micropython/discussions/14490 form efficient CRC calculation

No dependency, only micropython included modules
