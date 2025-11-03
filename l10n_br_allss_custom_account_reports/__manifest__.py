# -*- coding: utf-8 -*-
{
    'name': "ALLSS - Custom Account Reports - Brazil Location",
    'summary': """
        ALLSS - Custom Reports for Accounting from Brazil
        Balance Account Analytic""",
    'description': """
        Balance account account analytic and tag
    """,
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'ALLSS Soluções em Sistemas',
    'company': 'ALLSS Soluções em Sistemas',
    'website': "https://allss.com.br",
    'contributors': [
        'Anderson Coelho (ALLSS Soluções em Sistemas)',
        'Yenny Delgado (ALLSS Soluções em Sistemas)',
    ],
    'category': 'Accounting',
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config.parameter.xml',
        'views/balance_account_structure.xml',
        'views/balance_account_analytic.xml',
        'wizard/balance_calculation_results_view.xml',
        'wizard/balance_account_group_view.xml',
    ],
    'demo': [],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
