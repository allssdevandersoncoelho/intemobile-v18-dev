# -*- coding: utf-8 -*-
# © 2025 ALLSS Soluções em Sistemas LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from lxml import objectify
from odoo import models, fields

class L10nBrAlssWizardNfeImport(models.TransientModel):
    _inherit = 'l10n.br.allss.wizard.nfe.import'

    def default_l10n_br_allss_picking_type_id(self):
        l10n_br_allss_picking_type_id = self.env['stock.picking.type'].sudo().with_company(self.company_id).search([
            ('code', '=', 'outgoing'),
            ('company_id', 'in', [self.company_id.id, False])
        ], limit=1)
        return l10n_br_allss_picking_type_id.id if l10n_br_allss_picking_type_id else None

    l10n_br_allss_group_id = fields.Many2one('account.group', 'Grupo Contábil', required=False)
    l10n_br_allss_picking_type_id = fields.Many2one('stock.picking.type', 
                                                    string='Tipo de Operação'
                                                    # default=default_l10n_br_allss_picking_type_id,
                                                    # domain="[('company_id', '=', company_id)]"
                                                    )
    
    l10n_br_allss_journal_id = fields.Many2one('account.journal', 'Diário')
    l10n_br_allss_account_analytic_id = fields.Many2one('account.analytic.account', 'Conta Analítica')
    l10n_br_allss_account_account_id = fields.Many2one('account.account', 'Conta Contábil (Fatura)', required=True)




    def _l10n_br_allss_import_xml(self, auto, xml):
        nfe = objectify.fromstring(xml)
        obj_account_move = self.env['account.move'].sudo().with_context(l10n_br_allss_group_id=self.l10n_br_allss_group_id,
                                                                        l10n_br_allss_picking_type_id=self.l10n_br_allss_picking_type_id,
                                                                        l10n_br_allss_journal_id=self.l10n_br_allss_journal_id,
                                                                        l10n_br_allss_account_analytic_id=self.l10n_br_allss_account_analytic_id,
                                                                        l10n_br_allss_account_account_id=self.l10n_br_allss_account_account_id
                                                                        ).sudo()
        company_id = self.env.company.sudo()

        move = obj_account_move.import_nfe(
            auto, company_id, nfe, xml, False,
            company_id.l10n_br_allss_partner_automation,
            company_id.l10n_br_allss_invoice_automation, 
            company_id.l10n_br_allss_tax_automation,
            company_id.l10n_br_allss_supplierinfo_automation, 
            fiscal_position_id=company_id.l10n_br_allss_fiscal_position_id_automation or False, 
            account_move_dict=False,
            purchase_order_automation=company_id.l10n_br_allss_purchase_order_automation
        )

        if move and self.l10n_br_allss_picking_type_id:
            move.write({
                'l10n_br_allss_picking_type_id': self.l10n_br_allss_picking_type_id.id
            })
        
        return True if obj_account_move else False
