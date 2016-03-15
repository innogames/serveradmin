# -*- coding: utf-8 -*-
import os
from copy import deepcopy
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from serveradmin.dataset import query, filters, DatasetError
from pprint import pprint

datacenters = {
    's198.1': {
        'name': 'Süderstraße S198.1',
        'rowgroups': [
                [
                    {
                        'row': 'A',
                        'columns': ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14'],
                        'rowseparator': 'hot',
                    },
                ],
                [
                    {
                        'row': 'B',
                        'columns': ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14'],
                        'rowseparator': 'hot',
                        'static': {
                            '07': 'Storage',
                        }

                    },
                ],
                [
                    {
                        'row': 'C',
                        'columns': ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14'],
                        'rowseparator': 'hot',
                    }
                ],
                [
                    {
                        'row': 'D',
                        'columns': ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14'],
                        'rowseparator': 'hot',
                        'static': {
                            '03': 'Work rack',
                        }

                    }
                ],
                [
                    {
                        'row': 'E',
                        'columns': ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14'],
                        'rowseparator': 'hot',
                    }
                ],
        ],
    },
    'w408.1': {
        'name': 'Wendenstraße W408.1',
        'rowgroups': [
            [
                {
                    'row': 'D',
                    'columns': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
                    'rowseparator': 'cold',
                },
            ],
            [
                {
                    'row': 'C',
                    'columns': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
                    'rowseparator': 'hot',
                },
            ],
            [
                {
                    'row': 'B',
                    'columns': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
                    'rowseparator': 'cold',
                },
                {
                    'row': 'F',
                    'columns': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
                    'rowseparator': 'cold',
                },
            ],
            [
                {
                    'row': 'A',
                    'columns': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
                },
                {
                    'row': 'E',
                    'columns': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
                },
            ],

        ],
    },
    'w408.2': {
        'name': 'Wendenstraße W408.2',
        'rowgroups': [
            [
                {
                    'row': 'B',
                    'columns': ['1', '2', '3', '4', '5', '6', '7', '8', '9',],
                    'rowseparator': 'cold',
                },
                {
                    'row': 'D',
                    'columns': ['1', '...', '8'],
                    'rowseparator': 'cold',
                },
                {
                    'row': 'F',
                    'columns': ['1', '2', '3', '4', '5', '6', '7', '8'],
                    'rowseparator': 'cold',
                },

            ],
            [
                {
                    'row': 'A',
                    'columns': ['1', '2', '3', '4', '5', '6', '7', '8', '9',],
                },
                {
                    'row': 'C',
                    'columns': ['1', '...', '8'],
                },
                {
                    'row': 'E',
                    'columns': ['1', '2', '3', '4', '5', '6', '7', '8'],
                },
            ],
        ]
    },
}

@login_required
def index(request):

    # Do not work on configuration.
    dcs = deepcopy(datacenters)

    for dc_k, dc_v in dcs.iteritems():
        for rgroup in dc_v['rowgroups']:
            for row in rgroup:
                row['igcolumns'] = []
                for col in row['columns']:
                    if row['row'] != '_' and col != '_':
                        rack_attr = '{}-{}{}'.format(dc_k, row['row'], col)
                        hardware = query(
                            rack = rack_attr,
                            cmc_slot = filters.Empty()
                        )
                    row['igcolumns'].append( {
                        'style': 'extreme' if [ hw for hw in hardware if 'arch' in hw and hw['arch']=='EX670' ] else 'normal',
                        'name': col,
                        'ighw': len(hardware) if hardware else 0,
                        'hw': [ hw['hostname'] for hw in hardware],
                        'static': row['static'][col] if 'static' in row and col in row['static'] else None,
                    })
    pprint(dcs)
    return TemplateResponse(request, 'colo/index.html', {
        'dcs': dcs,
    })
