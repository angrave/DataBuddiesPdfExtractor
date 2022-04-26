# DataBuddies Pdf Extractor
This utility extract data from the DataBuddies pdf reports

# Set up dependencies
This script uses pdfplumber. The following might work for you.

```sh
pip install -r requirements.txt
```

# Run it ...

```sh
python3 dataextractor.py

Example Usage: dataextractor.py mydata.pdf
        This script extracts data from DataBuddy reports.
        Do not trust the output without manually verifying data in the pdf.
        It creates a single json file in the same directory mydata.json
        And hundreds of tsv files in the mydata-tsvs sub-directory
```
