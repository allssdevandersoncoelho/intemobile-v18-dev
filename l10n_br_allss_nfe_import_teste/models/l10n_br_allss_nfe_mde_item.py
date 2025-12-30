# -*- coding: utf-8 -*-

from odoo import models
from odoo import fields
from odoo import api


class L10nBrAllssNfeMdeItem(models.Model):
    _name = 'l10n.br.allss.nfe.mde.item'
    _description = "Itens do Manifesto do Destinatário da NF-e"

    l10n_br_allss_nfe_mde_id = fields.Many2one('l10n.br.allss.nfe.mde', 'MDF-e')
    l10n_br_allss_product_id = fields.Many2one(
        'product.product', 'Produto', help='Produto do XML já identificado no cadastro.')
    l10n_br_allss_fiscal_position_id = fields.Many2one('account.fiscal.position', 'Posição Fiscal')
    l10n_br_allss_cprod = fields.Char('Código', help='Tag cProd no XML.')
    l10n_br_allss_cean = fields.Char('Código de Barras', help='Tag cEAN no XML.')
    l10n_br_allss_xprod = fields.Char('Descrição', help='Tag xProd no XMl.')
    l10n_br_allss_ncm = fields.Char('NCM', help='Tag NCM no XML.')
    l10n_br_allss_cfop_id = fields.Many2one('l10n.br.allss.fiscal.cfop', 'CFOP',
                                            help='CFOP do XML já identificado no cadastro.')
    l10n_br_allss_ucom = fields.Char('Unidade', help='Tag uCom no XML.')
    l10n_br_allss_qcom = fields.Float('Quantidade', help='Tag qCom no XML.')
    l10n_br_allss_vuncom = fields.Float('Valor Unitário', help='Tag vUnCom no XML.')
    l10n_br_allss_vprod = fields.Float('Valor Total', help='Tag vProd no XML.')
    l10n_br_allss_tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string="Impostos",
        context={'active_test': False},
        check_company=True,
        help="Impostos do XML já identificados no cadastro.")
    l10n_br_allss_xped = fields.Char('Pedido', help='Tag xPed no XML.')
    l10n_br_allss_nitemped = fields.Char('Item do Pedido', help='Tag nItemPed no XML.')
    l10n_br_allss_taxation_ids = fields.One2many('l10n.br.allss.nfe.mde.item.taxation',
                                                 'l10n_br_allss_nfe_mde_item_id')
    l10n_br_allss_nitem = fields.Integer('Número do Item no XML')
    l10n_br_allss_purchase_order_id = fields.Many2one(
        'purchase.order', 'Ped. Compra',
        help='Pedido de compras a ser vinculado a Fatura deste processo de DF-e.', 
        # tracking=True,
        copy=False)
    l10n_br_allss_purchase_order_line_id = fields.Many2one(
        'purchase.order.line', 'Item Pedido',
        help='Item do pedido de compras a ser vinculado a Fatura deste processo de DF-e.',
        # tracking=True, 
        copy=False)

    def l10n_br_allss_open_nfe_mde_item_form(self):
        """
        Método responsável por abrir o item em uma visão do tipo 'form'.
        :return: dicionário com a Ação de Janela correspondente.
        """
        return {
            "name": "Item",
            "help": "Aqui você visualiza a tributação do item.",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": self._name,
            "res_id": self.id,
            'view_id': self.env.ref(
                'l10n_br_allss_nfe_import_teste.view_l10n_br_allss_nfe_mde_item_form').id,
            "target": "new",
        }

    @api.onchange('l10n_br_allss_purchase_order_id')
    def l10n_br_allss_onchange_purchase_id(self):
        self.l10n_br_allss_purchase_order_line_id = False


    @api.onchange('l10n_br_allss_purchase_order_line_id')
    def onchange_l10n_br_allss_purchase_order_line_id(self):
        if self.l10n_br_allss_purchase_order_line_id:
            self.l10n_br_allss_product_id = self.l10n_br_allss_purchase_order_line_id.product_id.id
