import os
import os.path

from legislationparser import LegislationParser

this_path = os.path.abspath(os.path.dirname(__file__))


def test_real_data():
    data_dir = os.path.join(this_path, 'data')
    for fname in os.listdir(data_dir):
        path = os.path.join(data_dir, fname)

        print("Testing ", path)
        with open(path, 'r') as f:
            lp = LegislationParser(f.read())

        body = lp.get_body()
        if fname != '2019s632.xml':
            assert len(body) > 200
        lp.get_preamble()
        lp.get_metadata()
        lp.get_schedules()
