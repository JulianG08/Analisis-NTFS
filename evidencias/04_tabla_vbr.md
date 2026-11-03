# Tabla 2.1 - Campos del VBR de NTFS (valores reales de ntfs_lab.img)

| Offset | Campo | Bytes | Valor hexadecimal | Valor decimal / interpretacion |
|---|---|---|---|---|
| 0x00-0x02 | Instruccion de salto (JMP) | 3 | `eb5290` | Salto al codigo de arranque |
| 0x03-0x0A | OEM ID | 8 | `4e54465320202020` | `NTFS    ` |
| 0x0B-0x0C | Bytes por sector | 2 | `0002` | 512 |
| 0x0D | Sectores por cluster | 1 | `08` | 8 |
| 0x0E-0x0F | Sectores reservados | 2 | `0000` | 0 |
| 0x15 | Descriptor de medio | 1 | `f8` | 0xF8 = disco fijo |
| 0x18-0x19 | Sectores por pista | 2 | `3f00` | 63 |
| 0x1A-0x1B | Cabezas | 2 | `ff00` | 255 |
| 0x1C-0x1F | Sectores ocultos | 4 | `00080000` | 2048 (= inicio de la particion) |
| 0x28-0x2F | Total de sectores | 8 | `eff70f0000000000` | 1046511 (0xFF7EF) |
| 0x30-0x37 | LCN inicial de $MFT | 8 | `0400000000000000` | 4 |
| 0x38-0x3F | LCN inicial de $MFTMirr | 8 | `7eff000000000000` | 65406 |
| 0x40 | Tamano de registro MFT | 1 | `f6` | -10 -> 2^10 = 1024 bytes |
| 0x44 | Tamano de registro de indice | 1 | `01` | 1 cluster = 4096 bytes |
| 0x48-0x4F | Numero de serie del volumen | 8 | `81f31c7a282d8e0d` | 0x0D8E2D287A1CF381 |
| 0x1FE-0x1FF | Firma de arranque | 2 | `55aa` | 55 AA |
