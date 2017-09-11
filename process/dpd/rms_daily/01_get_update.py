import sqlalchemy, odo, pandas, os, re, math

user = os.environ['RMS_USER']
pword = os.environ['RMS_PASS']
host = os.environ['RMS_HOST']
db = os.environ['RMS_DB']

rms_engine = sqlalchemy.create_engine('mssql+pymssql://{}:{}@{}/{}'.format(user, pword, host, db))
rms_connection = rms_engine.connect()

tablename = "vwRMS_Portal"

df = pandas.read_sql("""select * from dbo.{}""".format(tablename), rms_connection)
      
print("{} incidents found...".format(len(df)))

df.columns = df.columns.str.lower().str.replace(' ', '_')

# remove big spaces
space_re = re.compile(r'\s+')
df['address'] = df['address'].apply(lambda x: re.sub(space_re, ' ', x))

# leading address regex
address_re = re.compile(r'^[0-9]{1,}\s')

def block_from_number(number):
    blocknum = math.floor(number/100)*100
    if blocknum == 0:
        blocknum = 100
    return blocknum

def anonymize_location(value):
    separators = ['/','@','&', ' AND ']
    matched = False
    for s in separators:
        if value.find(s) > 0:
            matched = True
            if address_re.match(value):
                intersection = value.lstrip(address_re.match(value).group())
                return (value, "Corner of {} and {}".format(intersection.split(s)[0], intersection.split(s)[1]))
            else:
                return (value, "Corner of {} and {}".format(value.split(s)[0], value.split(s)[1]))
    if not matched:
        if address_re.match(value):
            housenum = int(address_re.match(value).group())
            return (value, "{} block of {}".format(block_from_number(housenum), value[len(address_re.match(value).group()):]))
        else:
            return (value, value)

# apply address function
df['address'] = df['address'].apply(lambda x: anonymize_location(x)[1])

def spell_ouil(value):
    if value == 'OUIL':
        value = 'OPERATING UNDER THE INFLUENCE OF LIQUOR OR DRUGS'
    else:
        pass

    return value

# apply ouil function
df['offense_category'] = df['offense_category'].apply(lambda x: spell_ouil(x))

# convert GEOX and GEOY to X, Y for making a point
df['x'] = df['geox'].apply(lambda x: float(x)/100)
df['y'] = df['geoy'].apply(lambda x: float(x)/100)
df.drop(['geox', 'geoy'], axis=1, inplace=True)

# send it to Postgres
odo.odo(df, 'postgresql://{}/{}::rms_update'.format(os.environ['PG_CONNSTR'], os.environ['PG_DB']))