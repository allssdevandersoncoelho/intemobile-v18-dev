# -*- coding: utf-8 -*-

from odoo import models, fields, api


class L10nBrAllssResCompany(models.Model):
    _inherit = 'res.company'

    l10n_br_allss_last_nsu_nfe = fields.Char("Último NSU usado", size=20, default='0')
    l10n_br_allss_manifest_automation = fields.Boolean(
        string="Ciência da operação", help="Quando marcado, executa a\
        ciência da operação, realiza o download das respectivas NF-e's e gera as faturas.")
    l10n_br_allss_partner_automation = fields.Boolean(
        string="Cadastra parceiro", help="Quando marcado, cadastra\
        automaticamente o parceiro caso o mesmo não na exista.")
    l10n_br_allss_fiscal_position_id_automation = fields.Many2one('account.fiscal.position', 
                                                                  string='Posição Fiscal',
                                                                  help='Posição Fiscal default definida para as '
                                                                       'importações de arquivo XML, utilizada '
                                                                       'quando a posição não for encontrada pela '
                                                                       'natureza da operação.')
    l10n_br_allss_invoice_automation = fields.Boolean(
        string="Registra fatura", help="Quando marcado, cria uma nova fatura\
        baseada nas informações da NF-e importada.")
    l10n_br_allss_tax_automation = fields.Boolean(
        string="Cadastra impostos", help="Quando marcado, cria um imposto\
        com uma nova aliquota, caso a mesma não exista.")
    l10n_br_allss_supplierinfo_automation = fields.Boolean(
        string="Cadastra produto do parceiro", help="Quando marcado, cria\
        cria um novo produto do parceiro, baseado nas informações da ordem de\
        compras informada na NF-e.")
    l10n_br_allss_purchase_order_automation = fields.Boolean(
        string="Cadastra pedido de compra",
        help="Quando marcado e o pedido de compra não for identificado, cria um novo pedido, "
             "baseado nas informações da ordem de compras informada na NF-e.")
    l10n_br_allss_vendor_journal_id = fields.Many2one(
        'account.journal', 'Diário para NF-e de Fornecedores', domain="[('type', '=', 'purchase')]",
        help="Quando definido, é usado na criação da fatura a partir de um XML de fornecedor.")


    @api.onchange('l10n_br_allss_partner_automation', 'l10n_br_allss_invoice_automation',
                  'l10n_br_allss_tax_automation', 'l10n_br_allss_supplierinfo_automation',
                  'l10n_br_allss_fiscal_position_id_automation')
    def _l10n_br_allss_set_manifest_automation(self):
        if not self.l10n_br_allss_manifest_automation and self.l10n_br_allss_partner_automation:
            self.l10n_br_allss_manifest_automation = True

        if not self.l10n_br_allss_manifest_automation and self.l10n_br_allss_invoice_automation:
            self.l10n_br_allss_manifest_automation = True

        if not self.l10n_br_allss_manifest_automation and self.l10n_br_allss_tax_automation:
            self.l10n_br_allss_manifest_automation = True

        if not self.l10n_br_allss_manifest_automation and self.l10n_br_allss_supplierinfo_automation:
            self.l10n_br_allss_manifest_automation = True

        if not self.l10n_br_allss_manifest_automation and self.l10n_br_allss_fiscal_position_id_automation:
            self.l10n_br_allss_manifest_automation = True


    @api.onchange('l10n_br_allss_tax_automation', 'l10n_br_allss_supplierinfo_automation')
    def _l10n_br_allss_set_invoice_automation(self):
        if not self.l10n_br_allss_invoice_automation and self.l10n_br_allss_tax_automation:
            self.l10n_br_allss_invoice_automation = True

        if not self.l10n_br_allss_invoice_automation and self.l10n_br_allss_supplierinfo_automation:
            self.l10n_br_allss_invoice_automation = True

