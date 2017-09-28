import os
import json


class DataManager:
    def __init__(self, wrk_dir):
        """
        Overall manager class, to handle scraped data. Upon initialization, creates the file structure to hold the
        output at the given working directory and builds a log file to record which files have been downloaded. Indexing
        within the log is country-specific, to reflect the numbering systems used by each country-level database.

        :param wrk_dir: directory at which to create the file structure.
        :return:
        """

        self.wrk_dir = wrk_dir.rstrip(os.sep)

        if not os.path.exists(self.wrk_dir):
            raise OSError('The given working directory does not exist!')
        else:
            self.data_path = '{1}{0}Legislative_Data'.format(os.sep, self.wrk_dir)
            self.log_path = '{1}{0}Legislative_Data{0}log.json'.format(os.sep, self.wrk_dir)

            if not os.path.exists(self.data_path):
                os.mkdir(self.data_path)
                os.mkdir('{1}{0}Legislation'.format(os.sep, self.data_path))

            if not os.path.exists(self.log_path):
                log_data = {'last updated': None}

                with open(self.log_path, 'wb') as f:
                    f.write(json.dumps(log_data))

            else:
                with open(self.log_path, 'rb') as f:
                    log_data = json.loads(f.read())

        self.log_data = log_data

    def update_data(self):
        """
        Wrapper function to run the various scrapers contained in the package and write the outputs. Also sets up file
        structure for output within each country. Initializes each scraper, and updates on-disk dataset based on the
        log file.

        Each scraper should have a scraper.data attribute which consists of a list of dictionaries, each of
        which holds metadata and text for each piece of legislation. Each entry should, at minimum, have a unique 'id'
        key, which is used to generate the file path for the output.
        """

        from datetime import datetime
        import _country_scrapers_annual
        _country_scrapers_annual = reload(_country_scrapers_annual)

        self.log_data['last updated'] = datetime.now().strftime('%m/%d/%Y')

        countries = [c for c in dir(_country_scrapers_annual) if '_' not in c]

        for country in countries:
            # initialize the file structure if working with a new country
            print country

            if country not in self.log_data:
                self.log_data[country] = []
                os.mkdir('{1}{0}Legislation{0}{2}'.format(os.sep, self.data_path, country.strip('_')))
                os.mkdir('{1}{0}Legislation{0}{2}{0}Annual'.format(os.sep, self.data_path, country.strip('_')))
                os.mkdir('{1}{0}Legislation{0}{2}{0}Consolidated'.format(os.sep, self.data_path, country.strip('_')))

            # Initialize the scraper for annual legislation for a given country, and write the output
            scraper = getattr(_country_scrapers_annual, country)(self.log_data, country)
            for entry in scraper.iter_data():
                out_path = '{1}{0}Legislation{0}{2}{0}Annual{0}{3}.json'.format(os.sep, self.data_path,
                                                                                country.strip('_'), entry['id'])
                with open(out_path, 'wb') as f:
                    f.write(json.dumps(entry))

                self.log_data = scraper.log_data

                #write the updated log
                with open(self.log_path, 'wb') as f:
                    f.write(json.dumps(self.log_data))

    def append_parsed(self):
        import os
        import _country_parsers_annual
        _country_scrapers_annual = reload(_country_parsers_annual)

        countries = [c for c in dir(_country_scrapers_annual) if '_' not in c]

        base_dir = '{1}{0}Legislation{0}{2}{0}Annual{0}'.format(os.sep, self.data_path, '{0}')

        for country in countries:
            country_dir = base_dir.format(country)
            file_list = os.listdir(country_dir)

            for file_name in file_list:
                full_path = country_dir + file_name
                with open(full_path, 'rb') as f:
                    content = json.loads(f.read())

                manager = getattr(_country_parsers_annual, country)(full_path, content)
                manager.parse()

                with open(full_path, 'wb') as f:
                    f.write(json.dumps(manager.content))

    def append_auxiliary(self):
        import os
        import _country_auxiliary_annual

        countries = [c for c in dir(_country_auxiliary_annual) if '_' not in c]
        base_dir = '{1}{0}Legislation{0}{2}{0}Annual{0}'.format(os.sep, self.data_path, '{0}')
        aux_dir = '{1}{0}Auxiliary{0}'.format(os.sep, self.data_path)

        for country in countries:
            country_path = base_dir.format(country)
            file_list = [country_path + f for f in os.listdir(country_path)]

            appender = getattr(_country_auxiliary_annual, country)(file_list, aux_dir, country)
            appender.add_auxiliary()

    def extract_entities(self, write=True):
        import os
        import csv
        import _country_entities_annual

        _country_entities_annual = reload(_country_entities_annual)

        countries = [c for c in dir(_country_entities_annual) if '_' not in c]
        base_dir = '{1}{0}Legislation{0}{2}{0}Annual{0}'.format(os.sep, self.data_path, '{0}')
        out_path = '{1}{0}Out{0}out_new.csv'.format(os.sep, self.data_path)

        out = []

        for country in countries:
            country_dir = base_dir.format(country)
            file_list = os.listdir(country_dir)

            for file_name in file_list:
                import re
                # file_name = '112th-congress_house-bill_3321.json'
                print re.sub('_', '/', file_name).strip('.json')

                with open(country_dir + file_name, 'rb') as f:
                    content = json.loads(f.read())

                    if content['parsed']:
                        parser = getattr(_country_entities_annual, country)(content['parsed'])
                        parsed = parser.do_entity_extraction()
                        print parsed['edges']
                        raw_input('')
                        content['density'] = parsed['density']
                        content['total_edges'] = parsed['total_edges']
                        content['n_cosponsors'] = len(content['cosponsors'])

                        #if parsed['edges'] and raw_input('Draw graph?'):
                        #    Visualize(parsed['edges'])

                        out.append(content)

        if write:
            with open(out_path, 'wb') as f:
                writer = csv.DictWriter(f, fieldnames=['id', 'date', 'title', 'density', 'total_edges', 'topic',
                                                       'sponsor', 'dw', 'sponsor_party', 'sponsor_majority',
                                                       'n_cosponsors', 'control', 'president_party', 'commemorative'],
                                        extrasaction='ignore')
                writer.writeheader()
                writer.writerows(out)


class Visualize:
    def __init__(self, edge_data):
        import textwrap
        import networkx as nx

        self.edge_data = [('\n'.join(textwrap.wrap(edge[0].title().strip(), 20)),
                           '\n'.join(textwrap.wrap(edge[1].title().strip(), 20)),
                           edge[2]) for edge in edge_data]

        self.G = nx.Graph()
        weights = []
        for u, v, w in self.edge_data:
            self.G.add_edge(u, v, weight=w)
            weights.append(w)

        self.pos = nx.nx_pydot.graphviz_layout(self.G)
        self.draw()

    def draw(self):
        import matplotlib.pyplot as plt
        import networkx as nx

        plt.figure(figsize=(15, 15))
        nx.draw_networkx_nodes(self.G, self.pos, node_size=0, alpha=0, node_color='black')

        m = float(max([e[2] for e in self.edge_data]))
        for edge in self.edge_data:
            edge_list = [[edge[0], edge[1]]]
            nx.draw_networkx_edges(self.G, self.pos, edgelist=edge_list, width=10, alpha=(edge[2]/m)**2, edge_color='b')

        nx.draw_networkx_labels(self.G, self.pos, font_size=10, font_family='sans-serif')
        plt.axis('off')
        # plt.draw()
        # raw_input('')
        # plt.close()
        plt.savefig("/home/rbshaffer/Desktop/fig1.pdf", dpi=100)
