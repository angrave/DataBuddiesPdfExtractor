#!/usr/bin/env python3
import os, sys
import glob
import json
import pandas as pd

# Example code to Databuddies data
# read tab separated values (.tsv) into dataframes
# The table description is read from a separate text file
def readTSV(verbose):
    allTSVfiles = sorted(glob.glob("*/*.tsv"))
    allColumnNames = set()
    for file in allTSVfiles:
        df = pd.read_csv(file, delimiter="\t")

        fileNoExt = os.path.splitext(file)[0]
        source, index = os.path.basename(fileNoExt).split("-table-")
        index = index.replace("_", ".")

        with open(f"{file[:-4]}-title.txt") as fh:
            description = fh.read().strip()

        # DataBuddies_2020 6.7.7 In which ﬁeld do you intend to earn your highest degree? 3 rows
        # ['Question', 'Illinois-AW(%)', 'Illinois-BHN(%)', 'Illinois-Sig.', 'Similar-AW(%)', 'Similar-BHN(%)', 'Similar-Sig.']
        if verbose:
            print(source, index, description, f"{len(df)} rows")
            print(list(df.columns), end="\n\n")
        allColumnNames.update(list(df.columns))
    print(sorted(allColumnNames))


def readJSON(verbose):
    allJSONfiles = sorted(glob.glob("*.json"))
    allColumnNames = set()
    for file in allJSONfiles:
        print(file)
        with open(file) as fh:
            tables = json.load(fh)
            for t in tables:
                allColumnNames.update(t["header"])
                if verbose:
                    print(t["index"], t["description"], f"{len(t['data'])} rows")
                    print(t["header"], end="\n\n")
            print(f"{len(tables)} tables loaded")
        print(sorted(allColumnNames))


def main():
    if len(sys.argv) not in [2, 3]:
        print(f"Usage: {sys.argv[0]} [-v] tsv|json")
        print(
            "Reads all tsv files in subdirectories or json files in the current directory"
        )
        print("  -v  : verbose mode. Prints summary information about every table")
        sys.exit(0)
    action = sys.argv[-1]
    verbose = sys.argv[-2] == "-v"
    if action == "tsv":
        readTSV(verbose)
    elif action == "json":
        readJSON(verbose)


if __name__ == "__main__":
    main()
