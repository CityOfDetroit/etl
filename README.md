# etl
ETL repository for DoIT work. 

ETL means *extract-transform-load* data across systems. For example, Department X manages their data in an Oracle database, we retrieve it, process it by cleaning values or joining multiple tables, and then publish it on our open data portal for residents and other departments to easily consume. 

## Context

Each ETL has four steps, each with it's own .yml file:
- 00_metadata: Describes the process
- 01_extract: Gets the source data
- 02_transform: Cleans the data
- 03_load: Puts the data online

Depending on your data request, you might want to add a new view to an existing process (like DLBA or BSEED datasets for example), or create an entirely new process. If creating new, copy the four template .yml files in `example/` to a new folder under `process/`.

## Setup

Requires Python 3.5+ and preferably the Anaconda install.

`pip install -r requirements.txt` to install Python dependencies.

Copy `sample.env` to `.env` and add your secrets.

## Usage

```python
import etl
# load YMLs for a process
gl = etl.Process('project_greenlight')
# extract from sources
gl.extract()
# transform (operations & sql)
gl.transform()
# load to destinations
gl.load()
```

### 00_metadata.yml

```yml
name: <Title that describes this process, eg 'DLBA datasets'>
schema: <Postgres schema, eg 'dlba'>
```

### 01_extract.yml

An array of data sources to be extracted. 

Supported sources:
- `database` from `database.py`: An Oracle or SQLServer database
- `salesforce` from `salesforce.py`: A Salesforce query
- `smartsheet` from `smartsheet.py`: A Smartsheet
- `sftp` from `sftp.py`: A SFTP server with .csv files
- `api` for now specificially from `scf.py`: An endpoint of open 311 data

Roadmap:
- `api` support for other domains
- `airtable`?
- `googlesheet`?

```yml
- database:
    type: <oracle|sql-server>
    prefix: <Origin database prefix, eg tm for tidemark>
    source: <Origin table name, eg CASEMAIN>
    destination: <Postgres table name, eg bseed.casemain>
    fields:
      - <Optional list of field names>
      - <If excluded, select *>

- salesforce:
    object: <SF object, eg Case>
    destination: <Postgres table name, eg dlba.account>
    fields:
      - <Optional list of field names>
      - <If excluded, select *>

- smartsheet: 
    id: <Smartsheet id>
    table: <Postgres table name, eg mmcc>

- sftp:
    host: <Known SFTP host or domain name, eg novatus or moveit>
    destination: <Postgres table name, eg ocp.contracts>

- api:
    domain: <String that tells us which api, eg seeclickfix>
    destination: <Postgres table name, eg scf.issues>
```

### 02_transform.yml

An array of steps to clean the data, which can include casting data types, geocoding addresses, scrubbing values, etc. These execute in order, think about them like steps in a recipe.

Supported options:
- `sql`: execute a list of custom SQL statements
- `geocode`: provide a table, address column, and geometry column
- `anonymize_geometry`: provide a table and a base to compare against, eg the centerline
- `anonymize_text_location`: provide a table, address column and set flag to keep track of which records have been anonymized

Roadmap:
- `join`?

```yml
- type: sql
  statements:
    - <drop view if exists...>
    - <create view...>

- type: geocode
  table: <Postgres table or view, eg bseed.mmcc>
  add_col: <Existing address field>
  geom_col: <Geometry field name to be created>

- type: anonymize_geometry
  table: <Postgres table or view, eg rms_update>
  against: <Postgres table, eg base.centerline>

- type: anonymize_text_location
  table: <Postgres table or view, eg rms_update>
  column: <Existing address field>
  set_flag: <Bool>
```

### 03_load.yml

An array of destinations to publish the data to.

Supported destinations:
- `Socrata`: A Socrata dataset
- `ArcGIS Online`: An ArcGIS Online feature layer
- `SFTP`: Drop a .csv on a SFTP server

Roadmap:
- `Mapbox`: A Mapbox tileset

```yml
- to: Socrata
  id: <Socrata 4x4; if blank, create new dataset> 
  name: <Dataset title>
  table: <Postgres view to load the data from, eg bseed.annual_inspections_socrata>
  method: <replace|upsert>
  row_identifier: <Field name, optional>
  columns:
    <Human-readable name>:
      field: <Field name in postgres view>
      type: <Socrata data type>

- to: ArcGIS Online
  id: <AGO id; if blank, create new layer>
  file: <Filename>
  table: <Postgres view to load the data from, eg fire.angels_night_ago>

- to: SFTP
  host: <Known SFTP host or domain name, eg crimescape>
  file: <Filename, eg /tmp/abc.csv>
```

## Scheduling jobs

We define jobs in `schedules.py` using [Schedule](https://schedule.readthedocs.io/en/stable/).

Schedule a new process like this:
```python
schedule.every.day.do(run, process='bseed', notify=True)
```

Wnen notify is `true`, we send success or error messages to Slack's #z_etl.
