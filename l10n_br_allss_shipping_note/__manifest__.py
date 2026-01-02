# -*- coding: utf-8 -*-
{
    'name': 'ALLSS - Shipping Note Template',
    'version': '18.0.1.0.0',
    'category': 'Invoice',
    'company': 'ALLSS Soluções em Sistemas',
    'website': 'https://allss.com.br',
    'author': 'ALLSS Soluções em Sistemas',
    'summary': 'Shipping Note with template in Brazilian molds',
    'description': 'Shipping Note with template in Brazilian molds',
    'license': 'AGPL-3',
    'contributors': [
        'Nathan Oliveira - nathan.oliveira@allss.com.br',
    ],
    'depends': [
        'account',
        'web',
        'base'
    ],
    'data': [
        #views
        'views/invoice.xml',

        #report
        'reports/shipping_note_report.xml',
        'reports/shipping_note_tml_report.xml',
    ],
    'images':['static/src/img/icon.jpg'],
    'demo': [
    ],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}