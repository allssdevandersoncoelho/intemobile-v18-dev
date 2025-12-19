# © 2025 ALLSS Soluções em Sistemas
# Part of ALLSS Soluções em Sistemas. See LICENSE file for full copyright and licensing details. License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{  # pylint: disable=C8101,C8103
    'name': 'ALLSS - [Vendas] Controle de XML (NF-e)',
    'sequence': 42,
    'version': '18.0',
    'summary': '''[Vendas] Importação de NFe (XML) de Vendas - by ALLSS Soluções em Sistemas.''',
    'description': '''Módulo de Importação de NFe (XML) relativo a NF-e Brasileira de Vendas - by ALLSS Soluções em Sistemas.''',
    'category': 'Account',
    'author': 'ALLSS Soluções em Sistemas',
    'maintainer': 'ALLSS Soluções em Sistemas',
    'website': 'https://allss.com.br',
    'support': 'suporte@allss.com.br',
    'license': 'AGPL-3',
    'license_file': 'LICENSE',
    'contributors': [
        'Caíque Anastácio - caique.anastacio@allss.com.br',
        'Anderson Coelho - anderson.coelho@allss.com.br',
    ],
    'depends': [
        'l10n_br_edi_stock',
        'l10n_br_allss_nfe_import',
    ],
    'data': [
        #data
        'data/account.fiscal.position_data.xml',
        
        #views
        'views/account_move.xml',
        'views/l10n_br_allss_codigo_marketplace.xml',

        #wizard
        'wizard/l10n_br_allss_wizard_nfe_import_view.xml',

        #security
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
