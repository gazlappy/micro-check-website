# Third-party notices

## Manufacturer cartridge lists

`src/assets/ink-official.json` is built by `tools/build_official_ink.py` from printer and cartridge names
read from the makers' own UK websites in October 2026 (raw data in `tools/data/`):

- HP: HP Support "HP ink and toner cartridge" table, Europe / Western Europe column (support.hp.com).
- Canon: Canon UK store "Ink & Toner by printer model" pages (canon.co.uk/store).
- Epson: "Compatible Main Units" on Epson UK ink product pages (epson.co.uk).

Only model names and cartridge codes are used, as facts for looking up the right cartridge. Brother's
websites do not permit automated collection, so Brother printers are covered only by the hand-checked list.

## PrinterTonerDB

`src/assets/ink-db.json` is derived from [kurcz/PrinterTonerDB](https://github.com/kurcz/PrinterTonerDB)
(`Printers2Toners.csv`), published under the [Apache License 2.0](licenses/PrinterTonerDB-Apache-2.0.txt).

Changes made: compatible, remanufactured, multipack and non-cartridge rows were removed; North American
cartridge numbers were converted to their UK equivalents, and rows without a well-established UK equivalent
were dropped; model names were tidied; printers were grouped by the cartridges they take. The conversion is
done by `tools/build_ink_db.py`.

The upstream data describes itself as scraped from a retail website and is not manufacturer-verified.
