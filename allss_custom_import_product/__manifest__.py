{
    'name': 'ALLSS - Marketplace',
    'description': '''Processo de importação de NF-e com validação pelo código do marketplace para vínculo do Produto''',
    'version': '18.0',
    'license': 'AGPL-3',
    'author': 'Renata Carrillo <nrenata.carrillo@allss.com.br>',
    'company': 'ALLSS Soluções em Sistemas',
    'website': 'https://allss.com.br',
    'depends': [
        'br_nfe_import',
        'stock',
        'stock_account',
        'purchase',
        'account',
        'br_nfe'
    ],
    'data': [
        # views
        'views/l10n_br_allss_codigo_marketplace.xml', ### ALLSS - 01/03/2024 - Renata Carrillo

        #security
        'security/ir.model.access.csv',
    ]
}
