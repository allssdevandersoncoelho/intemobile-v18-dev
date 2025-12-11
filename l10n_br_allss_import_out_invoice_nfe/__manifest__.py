# © 2023 Tiago Prates, ALLSS Soluções em Sistemas
# Part of ALLSS Soluções em Sistemas. See LICENSE file for full copyright and licensing details. License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{  # pylint: disable=C8101,C8103
    'name': 'ALLSS - [Vendas] Controle de XML (NF-e)',
    'sequence': 41,
    'version': '18.0',
    'summary': '''[Vendas]Importação de NFe (XML) - by ALLSS Soluções em Sistemas.''',
    'description': '''Módulo de Importação de NFe (XML) e Manifesto do Destinatário relativo a NF-e Brasileira - by ALLSS Soluções em Sistemas.''',
    'category': 'Account',
    'author': 'ALLSS Soluções em Sistemas',
    'maintainer': 'ALLSS Soluções em Sistemas',
    'website': 'https://allss.com.br',
    'support': 'suporte@allss.com.br',
    'license': 'AGPL-3',
    'license_file': 'LICENSE',
    'contributors': [
        'Caíque Anastácio - caique.anastacio@allss.com.br',
    ],
    'depends': [
        'l10n_br_allss_nfe_import',
    ],
    
    'data': [
        #wizard
        'wizard/l10n_br_allss_wizard_nfe_import_view.xml',

        #views
        'views/action.xml',
        'views/menu.xml',
        'views/account_move.xml',
        # 'views/l10n_br_allss_codigo_marketplace.xml',

        #security
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
