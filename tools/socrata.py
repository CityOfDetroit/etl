import fire, sodapy, yaml, os
from sqlalchemy import create_engine
from slack import SlackMessage
import sys

import sodapy
soda_token = os.environ['SODA_TOKEN']
soda_user = os.environ['SODA_USER']
soda_pass = os.environ['SODA_PASS']

FILEROOT = os.environ['ETL_ROOT']

class Dataset(object):
    def __init__(self, dir='dlba/sidelots'):
        self.directory = FILEROOT + 'process/' + dir
        with open(self.directory + '/config.yml', 'r') as f:
            self.conf = yaml.load(f)
        self.name = self.conf['name']
        self.cols = self.conf['socrata']['columns']
        self.view = self.conf['socrata']['view']
        self.table = self.conf['table']
        self.socrata_id = self.conf['socrata']['id']

        # let's connect to our DB
        if self.conf['backend'] == 'postgres':
            engine = create_engine('postgresql+psycopg2://{}/{}'.format(os.environ['PG_CONNSTR'], os.environ['PG_DB']))
        elif self.conf['backend'] == 'mysql':
            engine = create_engine('mysql+pymysql://{}/{}'.format(os.environ['MY_CONNSTR'], os.environ['MY_DB']))
        self.db_connection = engine.connect()

        # and connect to Socrata
        self.soda_connection = sodapy.Socrata('data.detroitmi.gov', soda_token, soda_user, soda_pass, timeout=54000)

    def desc(self):
        print("name:\t{}".format(self.name))
        print("url:\thttps://data.detroitmi.gov/resource/{}".format(self.socrata_id))
        print("table:\t{}".format(self.table))
        print("# cols:\t{}".format(len(self.cols)))

    def count_socrata(self):
        count = self.soda_connection.get(self.socrata_id, select='count({}) as count'.format(self.conf['socrata']['row_identifier']))
        self.socrata_count = int(count[0]['count'])
        return self.socrata_count

    def count_view(self):
        # get number of rows in view
        count_query = self.db_connection.execute("select count(*) from {}".format(self.view))
        self.view_count = int(count_query.fetchone()[0])
        return self.view_count

    def download(self):
        print("running {}/download.sh".format(self.directory))
        os.system("export FILEROOT={}; bash {}/download.sh".format(self.directory, self.directory))
        self.create_db_view()

    def update(self):
        print("running {}/update.sh".format(self.directory))
        os.system("export FILEROOT={}; bash {}/update.sh".format(self.directory, self.directory))

    def create_dataset(self):
        socrata_columns = [
            {
                "fieldname": c,
                "name": self.cols[c]['human'],
                "dataTypeName": self.cols[c]['type']
            }
            for c in self.cols ]

        new_dataset = self.soda_connection.create(self.conf['name'],
                                description = self.conf['description'],
                                columns = socrata_columns,
                                row_identifier = self.conf['socrata']['row_identifier'],
                                tags = self.conf['socrata']['tags'],
                                category = self.conf['socrata']['category'])

        self.socrata_id = new_dataset['id']
        self.soda_connection.publish(self.socrata_id)

    def send_update_msg(self, method):
        self.count_socrata()
        self.count_view()
        msg_txt = {
            "text": """Updating *{}* via `{}`\nNumber of rows in Socrata dataset: *{}*\nNumber of rows to replace: *{}*
                    """.format(self.conf['name'],
                               method,
                               self.socrata_count,
                               self.view_count)
        }
        msg = SlackMessage(msg_txt)
        msg.send()
        
    def replace(self):
        self.send_update_msg('REPLACE')
        rows = self.db_connection.execute("select * from {}".format(self.view))
        replace_payload = [ dict(row) for row in rows ]
        job = self.soda_connection.replace( self.socrata_id, replace_payload )
        return job

    def upsert(self):
        self.send_update_msg('UPSERT')
        rows = self.db_connection.execute("select * from {}".format(self.view))
        upsert_payload = [ dict(row) for row in rows ]
        for i in range(0, len(upsert_payload), 20000):
            try:
                r = self.soda_connection.upsert(self.socrata_id, upsert_payload[i:i+20000])
                print(r)
            except:
                print("Something went wrong on record {}".format(i))
                self.soda_connection.upsert(self.socrata_id, upsert_payload[i:i+20000])

    def create_db_view(self):
        columns = [ "{} as {}".format(self.cols[i]['expression'], i) for i in self.cols ]
        create_view_statement = """drop view if exists {}; create view {} as ( select {} from {} )""".format(self.view, self.view, ", \n".join(columns), self.table)
        self.db_connection.execute(create_view_statement)
        return create_view_statement
    
    def full_replace(self):
        self.download()
        self.replace()

if __name__ == "__main__":
    fire.Fire(Dataset)