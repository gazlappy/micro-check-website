# Third-party notices

## PrinterTonerDB

`src/assets/ink-db.json` is derived from [kurcz/PrinterTonerDB](https://github.com/kurcz/PrinterTonerDB)
(`Printers2Toners.csv`), published under the [Apache License 2.0](licenses/PrinterTonerDB-Apache-2.0.txt).

Changes made: compatible, remanufactured, multipack and non-cartridge rows were removed; North American
cartridge numbers were converted to their UK equivalents, and rows without a well-established UK equivalent
were dropped; model names were tidied; printers were grouped by the cartridges they take. The conversion is
done by `tools/build_ink_db.py`.

The upstream data describes itself as scraped from a retail website and is not manufacturer-verified.
