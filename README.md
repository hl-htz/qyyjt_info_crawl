# QYYJT Info Crawler

A web crawler for extracting and processing enterprise information from QYYJT(企业预警通).

## Installation

```bash
pip install -r requirements.txt
```

## Usage
```python
# for enterprise basic information extration:
python enterprise_crawl.py
```

```python
# for region economy information extraction:
python region_crawl.py
```

## Features

- Automated data extraction
- Information processing and storage
- Error handling and retry logic

## Modification

- Change `queries/enterprises.csv` or `queries/regions.csv` for target enterprises or regions

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies

## License

MIT