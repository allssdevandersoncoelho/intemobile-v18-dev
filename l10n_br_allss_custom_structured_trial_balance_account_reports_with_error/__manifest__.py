# -*- coding: utf-8 -*-
# l10n_br_allss_custom_structured_trial_balance_account_reports
{
    'name': "ALLSS - Custom Reports for Accounting from Brazil - Structured Trial Balance",
    'summary': """
        ALLSS - Balancete Estruturado Contábil
    """,
    'description': """
        Balancete Estruturado Contábil conforme as exigências brasileiras, com detalhamento por centro de custo e estrutura analítica.
    """,
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'ALLSS Soluções em Sistemas',
    'company': 'ALLSS Soluções em Sistemas',
    'website': "https://allss.com.br",
    'contributors': [
        'Anderson Coelho (ALLSS Soluções em Sistemas)',
        'Yenny Delgado (ALLSS Soluções em Sistemas)',
        'Caíque Anastácio (ALLSS Soluções em Sistemas)',
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
