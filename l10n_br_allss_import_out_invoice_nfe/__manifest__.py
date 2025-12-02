# © 2023 Tiago Prates, ALLSS Soluções em Sistemas
# Part of ALLSS Soluções em Sistemas. See LICENSE file for full copyright and licensing details. License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{  # pylint: disable=C8101,C8103
    'name': 'ALLSS - [Compras] Controle de XML (NF-e)',
    'sequence': 41,
    'version': '18.0',
    'summary': '''[Compras]Importação de NFe (XML) - by ALLSS Soluções em Sistemas.''',
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
        'l10n_br_allss_sales_nfe_import'
        'l10n_br_allss_eletronic_document_lc',
        'l10n_br_allss_purchase_order_tax',
    ],
    # 'external_dependencies': {
    #     'python': [
    #         'pytrustnfe', # 'pytrustnfe.nfe',
    #         # 'pytrustnfe.certificado', 'pytrustnfe.utils'
    #     ],
    # },
    'data': [
        # Data
        # 'data/ir_sequence.xml',
        # 'data/ir_config_parameter.xml',
        # 'data/ir_cron.xml',

        # Views
        # 'views/l10n_br_allss_nfe_mde_view.xml',
        # 'views/res_company_view.xml',
        # 'views/res_config_settings_view.xml',
        'wizard/l10n_br_allss_wizard_nfe_import_view.xml',
        # 'wizard/l10n_br_allss_wizard_nfe_schedule_view.xml',
        # 'wizard/l10n_br_allss_wizard_operation_not_performed_view.xml',
        # 'views/action.xml',
        'views/menu.xml',
        'views/account_move.xml',

        # Security Files
        # 'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
