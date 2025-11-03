# © 2025 Anderson Coelho, ALLSS Soluções em Sistemas
# Part of ALLSS Soluções em Sistemas. See LICENSE file for full copyright and licensing details. License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{  # pylint: disable=C8101,C8103
    'name': 'ALLSS - Importador de XML (NF-e) de clientes (Vendas)',
    'sequence': 42,
    'version': '18.0',
    'summary': '''Importação de NFe (XML) de clientes (Vendas) - by ALLSS Soluções em Sistemas.''',
    'description': '''Módulo de Importação de NFe (XML) de clientes (Vendas) - by ALLSS Soluções em Sistemas.''',
    'category': 'Account',
    'author': 'ALLSS Soluções em Sistemas',
    'maintainer': 'ALLSS Soluções em Sistemas',
    'website': 'https://allss.com.br',
    'support': 'suporte@allss.com.br',
    'license': 'AGPL-3',
    'license_file': 'LICENSE',
    'contributors': [
        'Tiago Prates - tiago.prates@allss.com.br',
        'Anderson Coelho - anderson.coelho@allss.com.br',
        'Caíque Anastácio - caique.anastacio@allss.com.br', 
    ],
    'depends': [
        'l10n_br_allss_nfe_import',
    ],
    'data': [
        # Data
        'data/ir_sequence.xml',
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',

        # Views
        'views/l10n_br_allss_nfe_mde_view.xml',
        'views/res_company_view.xml',
        'views/res_config_settings_view.xml',
        'wizard/l10n_br_allss_wizard_nfe_import_view.xml',
        'wizard/l10n_br_allss_wizard_nfe_schedule_view.xml',
        'wizard/l10n_br_allss_wizard_operation_not_performed_view.xml',
        'views/action.xml',
        'views/menu.xml',

        # Security Files
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
