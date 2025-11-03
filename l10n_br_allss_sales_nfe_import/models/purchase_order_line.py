# -*- coding: utf-8 -*-
# © 2023 Tiago Prates <tiago.prates@allss.com.br>, ALLSS Soluções em Sistemas LTDA

from odoo import fields, models, api


class L10nBrAllssPurchaseOrderLineNfeImport(models.Model):
    _inherit = 'purchase.order.line'

    l10n_br_allss_import_nfe_tax = fields.Text('Impostos da NF-e Importada')
