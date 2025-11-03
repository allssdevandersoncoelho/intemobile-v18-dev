# -*- coding: utf-8 -*-

from odoo import models, fields


class L10nBrAllssNfeMdeItemTaxation(models.Model):
    _name = 'l10n.br.allss.nfe.mde.item.taxation'
    _description = "Tributação dos Itens do Manifesto do Destinatário da NF-e"

    l10n_br_allss_nfe_mde_item_id = fields.Many2one('l10n.br.allss.nfe.mde.item', 'Item')
    l10n_br_allss_tax_id = fields.Many2one('account.tax', 'Imposto')
    l10n_br_allss_base_calculo = fields.Float('Base de Cálculo')
    l10n_br_allss_aliquota = fields.Float('Alíquota')
    l10n_br_allss_valor = fields.Float('Valor')
    l10n_br_allss_cst = fields.Char('CST')
