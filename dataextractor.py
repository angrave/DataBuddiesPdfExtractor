#!/usr/bin/env python3
import os, sys
import json
import pdfplumber

# Replace "Your Institution" with ...
MyUni = "Illinois"

# Acme Databuddies pdf table extractor v.00001
# This extractor extracts section titles and tables from each page of the pdf
# It assumes that the order of titles is the same order of tables in each page.
#
# IMPORTANT:
# This extractor is only lightly tested and therefore, buggy and fragile.
# It makes several assumptions about the layout and parsing of the Databuddies pdf.
#
# It is critical to manually verify the output against the tables presented
# in the original pdf prior to any publication or decision or use of the
# extracted data generated by this tool generates
#
# If this work leads to presentations or publications an acknowledgement
# of the author(s) contribution: Lawrence Angrave and (Your name here?)
# would be appreciated.
#
# MIT Open source license
# https://opensource.org/licenses/MIT
#
# Send errors, ommissions, suggestions, coffee to angrave at illinois edu

# Section title extraction notes & various observations
# Section titles were in the form 'Table 1.2.3 A longer description here'
# The 3 reports (2018,2019,2020) had very different numbers of tables (100 - 200)
#
# Observed font names for section titles were consistent for the 3 input pdfs
# 2020: 'NKNIMF+CMSSBX10-10'
# 2019: 'OZYTHV+CMSSBX10-10'
# 2018: 'UPGGSD+CMSSBX10-10'
# CMSSBX10 = computer modern sans serif bold extended 10pt

# Example run-
# ./dataextractor.py ../../pdfs/DataBuddies_2018.pdf
# Reading page 66
# Writing ../../pdfs/DataBuddies_2018.json
# 111 tables written to ../../pdfs/DataBuddies_2018-tsv
# ./dataextractor.py ../../pdfs/DataBuddies_2019.pdf
# Reading page 106
# Writing ../../pdfs/DataBuddies_2019.json
# 201 tables written to ../../pdfs/DataBuddies_2019-tsv
# ./dataextractor.py ../../pdfs/DataBuddies_2020.pdf
# Reading page 128
# Writing ../../pdfs/DataBuddies_2020.json
# 207 tables written to ../../pdfs/DataBuddies_2020-tsv


# Note reported font size can vary by a tiny amount; hence the rounding to the nearest point
# Font names appear to be in the form '<randomletters>+<Meaningfulname>''
def toFontInfo(info):
    return f"{info['fontname']}-{round(info['size'])}"


# returns a list of strings - the apparent section headings on the page
# If we're lucky there will be the same number of headings as tables (and in the same order)
# A typical string is in the form, 'Table 1.2.3 What is your favorite llama?'
def extractTableHeadings(page):
    allpagewords = page.extract_words(
        use_text_flow=True, extra_attrs=["fontname", "size"]
    )
    results = []
    expectedFontName = "+CMSSBX10-"  # True for all pdfs processed so far (2018-2020)
    # "+CMSSBX10-25" for Table of Contents
    yPositions = []  # Expect headings to be vertically ordered
    # State machine
    isBuilding = False
    headingFontInfo = ""
    partial = []

    for i, wordInfo in enumerate(allpagewords):
        lastElement = i == len(allpagewords) - 1
        if not isBuilding and "Table" == wordInfo["text"]:
            # We could require round(fontsize) to be 10 not 25 (="Table of Contents")
            yPositions.append(wordInfo["top"])
            isBuilding = True
            headingFontInfo = toFontInfo(wordInfo)
            assert expectedFontName in headingFontInfo, headingFontInfo

        if toFontInfo(wordInfo) != headingFontInfo:
            isBuilding = False
        if isBuilding:
            partial.append(wordInfo["text"])
        elif (lastElement or not isBuilding) and partial:
            results.append(" ".join(partial))
            partial = []
    assert isIncreasing(yPositions), yPositions
    ignore = "Table layout"
    # Table of Contents
    results = [item for item in results if item.split(" ")[1][0] in "0123456789"]
    return results


def noneToEmpty(item):
    return "" if item is None else item


def filterPercentAfterDigit(item):
    # Looking for strings that end with a percentage char
    if item is None or len(item) < 2 or item[-1] != "%":
        return item
    # If preceeding character was a number then drop the percentage char
    if item[-2] in "0123456789":
        return item[:-1]
    return item


assert filterPercentAfterDigit("123%") == "123"
assert filterPercentAfterDigit("123") == "123"

# Expands mean and SD values into separate columns (see asserted example below)
def expandMeanSDFromRowAll(row):
    result = [row[0]]
    for item in row[1:]:
        if (" (" in item) and (item[-1] == ")"):
            items = item[:-1].split(" (")
            result.extend(items)
        else:
            result.append(item)
    return result


assert expandMeanSDFromRowAll(["a", "1 (2)", "b"]) == ["a", "1", "2", "b"]

# Ensure all columns have a name (see asserted example below)
# Returns a new list where empty column headings are replaced with Column<i>
def addNameForEmptyColumnNames(header):
    return [
        item if len(item) > 0 else f"Column{idx+1}" for idx, item in enumerate(header)
    ]


assert addNameForEmptyColumnNames(["", "A", ""]) == ["Column1", "A", "Column3"]

# assert that column names are unique
def noDuplicateColumnNames(header):
    seen = set()
    for h in header:
        assert h not in seen, f"Duplicate column {h} in {header}"
        seen.add(h)


# Expand Mean and SD header into 2 columns (see asserted example below)
def expandHeaderMeanSD(header):
    result = []
    for h in header:
        if h.endswith("Mean (SD)"):
            result.extend([f"{h[:-9]}-Mean", f"{h[:-9]}-SD"])
        else:
            result.append(h)
    return result


assert expandHeaderMeanSD(["a", "bMean (SD)", "c"]) == ["a", "b-Mean", "b-SD", "c"]

# Do the dirty work of parsing a data buddies table
# They have different formats but the basic outline is
# Discard the unwanted footer
# Build a single row header from multiple rows
# Discard '%' in the data values


def processOneTable(section, table):
    # example footnote:
    # '(*) p≤.05 and Cohen’s d or h≥.30; (N/A) n<5 or test criteria were not met'

    # Consume end rows that are footnotes i.e. text in the first column, everything else None
    while True:
        lastRow = table[-1]
        remainderCols = lastRow[1:]
        if any([item is not None for item in remainderCols]):
            break
        # print(lastRow)
        table = table[:-1]

    # Convert None to empty strings
    table = [[noneToEmpty(item) for item in row] for row in table]

    # Watch out for Triple row headers :-)
    # [['', 'Your Institution', '', '', 'Similar Institutions', '', ''], ['', 'Women', 'Men', '', 'Women', 'Men', '']]

    if table[1][0] == "":
        h1 = table[0]
        # The only example I've seen so far, so hard code for it
        assert h1 == [
            "",
            "Your Institution",
            "",
            "",
            "Similar Institutions",
            "",
            "",
        ], h1
        h2 = table[1]
        assert len(h2) == 7, h2
        assert h2[1] == h2[4] and h2[2] == h2[5], h2  # Women Men .. Women Men
        header = [
            "",
            f"{MyUni}-{h2[1]}" + ,
            f"{MyUni}-{h2[2]}" + ,
            f"{MyUni}-",
            f"Similar-{h2[4]}",
            f"Similar-{h2[5]}" ,
            "Similar-",
        ]
        # And on the third row we pick up "Sig" too
        h3 = table[2]
        assert h3[0] == "" and len(h3) == len(header), h3
        # For every column, append the last row item
        header = list(map(lambda x: "".join(x).strip(), zip(header, h3)))
        datarows = table[3:]
    else:
        header = table[0]
        datarows = table[1:]

    if header == ["", "Your Institution Similar Institutions\nSig.\n(%) (%)", "", ""]:
        header = ["", f"{MyUni} (%)", "Similar (%)", "Sig."]

    elif header == [
        "",
        "Your Institution Similar Institutions\nSig.\nMean (SD) Mean (SD)",
        "",
        "",
    ]:
        header = [
            "",
            f"{MyUni}-Mean",
            f"{MyUni}-SD",
            "Similar-Mean",
            "Similar-SD",
            "Sig",
        ]

    if header[0] == "":
        header[0] = "Question"

    header = expandHeaderMeanSD(header)
    datarows = [expandMeanSDFromRowAll(row) for row in datarows]

    datarows = [[filterPercentAfterDigit(item) for item in row] for row in datarows]

    # Check and fix Ragged rows.
    # The last row may be just the absolute counts and can be short
    # Other rows may skip the last column if there is no "*" to report
    for row in datarows:
        if row[0] != "n":
            assert len(row) == len(header) or len(row) + 1 == len(
                header
            ), f"{section}:{header}\n{row}"
        if len(row) < len(header):
            row.extend([""] * (len(header) - len(row)))

    assert "Your Institution" not in " ".join(header), f"{section}:{header}"
    assert "Similar Institutions" not in " ".join(header), f"{section}:{header}"

    header = addNameForEmptyColumnNames(header)  # e.g. 'Column1'
    noDuplicateColumnNames(header)  # e.g. 'Column1'

    sectionAsWords = section.split(" ")
    assert sectionAsWords[0] == "Table", sectionAsWords
    index = sectionAsWords[1]
    assert ("." in index) and (index[0] in "0123456789"), index
    description = " ".join(sectionAsWords[2:])
    return {
        "index": sectionAsWords[1],
        "description": description,
        "header": header,
        "data": datarows,
    }


def writeJson(jsonFilename, alldata):
    with open(jsonFilename, "w", encoding="utf8") as fh:
        json.dump(alldata, fh)


def writeOneTableTSV(outputbase, one):
    index = one["index"]
    tsvFilename = f"{outputbase}-table-{index.replace('.','_')}.tsv"
    titleFilename = os.path.splitext(tsvFilename)[0] + "-title.txt"
    # print(tsvFilename,end='\r')
    separator = "\t"

    with open(tsvFilename, "w", encoding="utf8") as fh:
        print(separator.join(one["header"]), file=fh)
        for row in one["data"]:
            print(separator.join(row), file=fh)

    with open(titleFilename, "w", encoding="utf8") as fh:
        print(one["description"], file=fh)


def isDataTable(table):
    if len(table) > 2:
        return True
    headings = "".join([noneToEmpty(item) for item in table[0]])
    assert len(headings) == 0, headings
    return False


def isIncreasing(list):
    if len(list) < 2:
        return True
    return all(a < b for a, b in zip(list[:-1], list[1:]))


assert not isIncreasing([6, 7, 7, 8])
assert isIncreasing([2, 3, 5, 6])


def readDataBuddiesTables(inputPath):
    tableData = []
    table_settings = {}
    # In addition to the content we need the Y position of each table, so portions of this code is based on
    # The implementation of extract_tables
    # https://github.com/jsvine/pdfplumber/blob/18a27516c5e5a9efd6bcb3c1639aed2017777621/pdfplumber/page.py#L223
    #
    resolved_settings = pdfplumber.page.TableFinder.resolve_table_settings(
        table_settings
    )
    extract_kwargs = {
        k: table_settings["text_" + k]
        for k in ["x_tolerance", "y_tolerance"]
        if "text_" + k in table_settings
    }

    with pdfplumber.open(inputPath) as pdf:
        for loopIndex, page in enumerate(pdf.pages):
            print(f"\rReading page {loopIndex +1}", flush=True, end="")
            tableHeadings = extractTableHeadings(page)

            pdfTables = page.find_tables(resolved_settings)
            # assert that tables are vertically ordered
            yPositions = list(map(lambda t: t.bbox[1], pdfTables))
            assert isIncreasing(yPositions)

            tables = [t.extract(**extract_kwargs) for t in pdfTables]
            # END
            # Early pages have some blank tables comprised of empty strings and None
            tables = [t for t in tables if isDataTable(t)]

            assert len(tableHeadings) == len(
                tables
            ), f"{tableHeadings}. Expected {len(tables)}\n{tables}"
            for heading, table in zip(tableHeadings, tables):
                one = processOneTable(heading, table)
                tableData.append(one)
    return tableData


def main():
    if len(sys.argv) != 2:
        print(
            f"""Example Usage: {sys.argv[0]} mydata.pdf
        This script extracts data from DataBuddy reports.
        Do not trust the output without manually verifying data in the pdf.
        It creates a single json file in the same directory as the input file
        And hundreds of tsv files in a new sub-directory (e.g. mydata-tsvs).
        Send bug reports and suggestions to angrave at illinois edu
        Latest version at https://github.com/angrave/DataBuddiesPdfExtractor
        """
        )
        sys.exit(0)

    inputPath = sys.argv[1]
    assert inputPath.endswith(".pdf")
    inputPathNoExt = os.path.splitext(inputPath)[0]

    allData = readDataBuddiesTables(inputPath)

    outputJsonPath = f"{inputPathNoExt}.json"
    print(f"\nWriting {outputJsonPath}")
    writeJson(outputJsonPath, allData)

    outputTSVDir = f"{inputPathNoExt}-tsv"
    outputTSVBase = f"{outputTSVDir}/{os.path.basename(inputPathNoExt)}"
    os.makedirs(outputTSVDir, exist_ok=True)
    for table in allData:
        writeOneTableTSV(outputTSVBase, table)

    print(f"{len(allData)} tables written to {outputTSVDir}")


if __name__ == "__main__":
    main()
