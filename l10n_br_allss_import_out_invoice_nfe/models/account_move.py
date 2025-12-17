# -*- coding: utf-8 -*-
# © 2025 ALLSS Soluções em Sistemas LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

# import re
# import base64
# import pytz
import logging

_logger = logging.getLogger(__name__)

from odoo import fields, models             #, _, Command
# from dateutil import parser
# from datetime import datetime
# from lxml import objectify
from odoo.exceptions import UserError       #, ValidationError

# from odoo import api
# from contextlib import contextmanager


# def convert(obj, conversion=None):
#     if conversion:
#         return conversion(obj.text)
#     if isinstance(obj, objectify.StringElement):
#         return str(obj)
#     if isinstance(obj, objectify.IntElement):
#         return int(obj)
#     if isinstance(obj, objectify.FloatElement):
#         return float(obj)
#     raise f"Tipo não implementado {type(obj)}"


# def get(obj, path, conversion=None):
#     paths = path.split(".")
#     index = 0
#     for item in paths:
#         if not item:
#             continue
#         if hasattr(obj, item):
#             obj = obj[item]
#             index += 1
#         else:
#             return None
#     if len(paths) == index:
#         return convert(obj, conversion=conversion)
#     return None


# def cnpj_cpf_format(cnpj_cpf):
#     if len(cnpj_cpf) == 14:
#         cnpj_cpf = (cnpj_cpf[0:2] + '.' + cnpj_cpf[2:5] +
#                     '.' + cnpj_cpf[5:8] +
#                     '/' + cnpj_cpf[8:12] +
#                     '-' + cnpj_cpf[12:14])
#     else:
#         cnpj_cpf = (cnpj_cpf[0:3] + '.' + cnpj_cpf[3:6] +
#                     '.' + cnpj_cpf[6:9] + '-' + cnpj_cpf[9:11])
#     return cnpj_cpf


class AllssAccountMoveNfeImport(models.Model):
    _inherit = 'account.move'
    
    def default_l10n_br_allss_picking_type_id(self):
        l10n_br_allss_picking_type_id = self.env['stock.picking.type'].sudo().with_company(self.company_id).search([
            ('code', '=', 'outgoing'),
            ('company_id', 'in', [self.company_id.id, False])
        ], limit=1)
        return l10n_br_allss_picking_type_id.id if l10n_br_allss_picking_type_id else None
    
    # def _compute_picking(self):
    #     for r in self:
    #         pickings = self.env['stock.picking'].sudo().search([('l10n_br_allss_account_move_id', '=', r.id)])
    #         if pickings:
    #             r.l10n_br_allss_picking_ids = [(6, 0, pickings.ids)]
    #             r.l10n_br_allss_picking_count = len(pickings)

    l10n_br_allss_picking_type_id = fields.Many2one('stock.picking.type', 
                                                    string='Tipo de Operação', 
                                                    default=default_l10n_br_allss_picking_type_id,
                                                    copy=False, 
                                                    store=True,
                                                    domain="[('company_id', '=', company_id)]")
    # l10n_br_allss_picking_ids = fields.Many2many('stock.picking', 
    #                                             #  compute='_compute_picking', 
    #                                              string='Picking', 
    #                                              copy=False, 
    #                                              store=True)
    # l10n_br_allss_picking_count = fields.Integer(string='Picking count', 
    #                                             #  compute='_compute_picking', 
    #                                              default=0, 
    #                                              store=True)


    def _l10n_br_get_pickings(self):
        ''' Override to include pickings linked via l10n_br_allss_account_move_id '''
        pickings = super()._l10n_br_get_pickings()

        extra_pickings = self.env["stock.picking"].search([
            ("l10n_br_allss_account_move_id", "=", self.id),
        ])

        return (pickings | extra_pickings).filtered(lambda p: p)



    # def import_nfe(self, auto, company_id, nfe, nfe_xml, dfe, 
    #                partner_automation=False,
    #                account_invoice_automation=False, 
    #                tax_automation=False,
    #                supplierinfo_automation=False, 
    #                fiscal_position_id=False,
    #                payment_term_id=False, 
    #                account_move_dict=None, 
    #                purchase_order_automation=False):

    #     _logger.warning(f"Contexto import_nfe:{self.env.context}")
    #     account_move_dict = account_move_dict or {}
    #     partner_vals = self._get_company_account_move(auto, nfe, partner_automation)
    #     if not partner_vals:
    #         return False
    #     _logger.warning(f">>>>> ALLSS > import_nfe > partner_vals: {partner_vals}")

    #     if self.existing_account_move(auto, nfe, partner_vals):
    #         # self.sudo().message_post(body='NF-e já importada!')
    #         if auto:
    #             _logger.warning(f'>>>>> ALLSS > NF-e Import > NF-e já importada!')
    #             return False
    #         else:
    #             raise UserError('NF-e já importada!')

    #     account_move_dict.update(self.get_compra(nfe))
    #     purchase_order = account_move_dict.get('l10n_br_allss_xpedcom')
    #     _logger.warning(f">>>>> ALLSS > import_nfe > purchase_order ({type(purchase_order)}): {purchase_order}")
    #     purchase_order_dict = self._l10n_br_allss_get_purchase_order_vals(purchase_order)       
    #     _logger.warning(f">>>>> ALLSS > import_nfe > purchase_order_dict ({type(purchase_order_dict)}): {purchase_order_dict}")

    #     company_id = self.env['res.company'].sudo().browse(partner_vals['company_id'])
        
    #     _logger.warning(f">>>>> ALLSS > import_nfe > company_id ({type(company_id)}): {company_id}")
        
    #     if not fiscal_position_id:
    #         fiscal_position_id = (purchase_order_dict and purchase_order_dict.get('fiscal_position_id')) or company_id.l10n_br_allss_fiscal_position_id_automation or False
        
    #     account_move_dict.update(partner_vals)
    #     account_move_dict.pop('destinatary')
    #     account_move_dict.update({
    #         'l10n_br_allss_nf_xml': base64.encodebytes(nfe_xml),
    #         'l10n_br_allss_nf_number': nfe.NFe.infNFe.ide.nNF,
    #         # 'name': nfe.NFe.infNFe.ide.nNF,
    #         'l10n_latam_document_number': nfe.NFe.infNFe.ide.nNF,
    #     })
    #     account_move_dict.update(self.get_protNFe(nfe, company_id))
    #     account_move_dict.update(self.get_main(nfe))
    #     partner = self.get_partner_nfe(
    #         nfe, partner_vals['destinatary'], partner_automation, dfe)
    #     account_move_dict.update(
    #         self.get_ide(nfe, partner_vals['move_type'], fiscal_position_id))
    #     account_move_dict.update(partner)
    #     if purchase_order_dict:
    #         account_move_dict.update(purchase_order_dict)
    #     account_move_dict.update(self.get_items(
    #         nfe, company_id, partner['partner_id'] or account_move_dict['partner_id'],
    #         account_move_dict, dfe,
    #         supplierinfo_automation, tax_automation, 
    #         fiscal_position_id=account_move_dict['fiscal_position_id'] \
    #                                 if 'fiscal_position_id' in account_move_dict \
    #                                         and account_move_dict['fiscal_position_id'] \
    #                                 else fiscal_position_id,
    #         purchase_order_id=purchase_order_dict and purchase_order_dict.get('purchase_id')
    #         or account_move_dict.get('purchase_id'),
    #         purchase_order_automation=purchase_order_automation
    #     ))
    #     # if not purchase_order_dict and purchase_order_automation:
    #     #     account_move_dict.update(self._l10n_br_allss_create_purchase_order_vals(
    #     #         account_move_dict, dfe))
    #     purchase_id = purchase_order_dict.get('purchase_id') or account_move_dict.get('purchase_id')
    #     if purchase_id:
    #         brw_purchase_order = self.env.get('purchase.order').sudo().browse(purchase_id)
    #         brw_purchase_order.state == 'draft' and brw_purchase_order.button_confirm()
    #     account_move_dict.update(self.get_infAdic(nfe))

    #     _logger.warning(f">>>>> ALLSS > import_nfe > move_type: {partner_vals['move_type']}")

    #     # invoice_default = self.env['account.move'].with_context(
    #     #     default_move_type=partner_vals['move_type'], default_company_id=company_id.id
    #     # ).default_get(['journal_id'])

    #     # journal_id = self.env['account.move'].with_context(
    #     #     force_company=company_id.id, 
    #     #     type=('sale' 
    #     #             if partner_vals['move_type']=='out_invoice' 
    #     #             else 'purchase')
    #     #     )._get_default_journal()

    #     tipo = 'sale' if partner_vals['move_type'] == 'out_invoice' else 'purchase'
    #     journal_id = self.l10n_br_allss_get_journal_id(company_id, tipo)

    #     _logger.warning(f">>>>> ALLSS > import_nfe > journal_id ({type(journal_id)}): {journal_id}")
    #     _logger.warning(f">>>>> ALLSS > import_nfe > journal_id.id ({type(journal_id.id)}): {journal_id.id}")
    #     _logger.warning(f">>>>> ALLSS > import_nfe > journal_id.name ({type(journal_id.name)}): {journal_id.name}")

    #     account_move_dict.update({'journal_id': journal_id.id})

    #     if 'l10n_br_allss_ms_code' not in account_move_dict and 'l10n_br_allss_ms_code' in journal_id._fields and journal_id.l10n_br_allss_ms_code:
    #         account_move_dict.update({'l10n_br_allss_ms_code': journal_id.l10n_br_allss_ms_code.sudo().id})

    #     transport_data = []
    #     transp_1 = self.get_transp(nfe)
    #     if transp_1:
    #         transport_data += transp_1
    #     mod_frete = '9'
    #     if hasattr(nfe.NFe.infNFe, 'transp'):
    #         mod_frete = get(nfe.NFe.infNFe.transp, 'modFrete', str)
        
    #     # ALLSS - Campo "l10n_br_allss_shipping_mode" substituido pelo "l10n_br_edi_freight_model" do módulo "l10n_br_edi"
    #     # account_move_dict.update({'l10n_br_allss_shipping_mode': mod_frete})
    #     # account_move_dict.update({'l10n_br_edi_freight_model': mod_frete})
    #     if mod_frete == "0":
    #         mod_frete = "CIF"
    #     elif mod_frete == "1":
    #         mod_frete = "FOB"
    #     elif mod_frete == "2":
    #         mod_frete = "Thirdparty"
    #     elif mod_frete == "3":
    #         mod_frete = "SenderVehicle"
    #     elif mod_frete == "4":
    #         mod_frete = "ReceiverVehicle"
    #     elif mod_frete == "9":
    #         mod_frete = "FreeShipping"
    #     else:
    #         mod_frete = ""
    #     account_move_dict.update({'l10n_br_edi_freight_model': mod_frete})

    #     transp_1 = self.get_reboque(nfe)
    #     if transp_1:
    #         transport_data += transp_1
    #     account_move_dict.update({'l10n_br_allss_trailer_ids': transport_data})
    #     account_move_dict.update({'l10n_br_allss_volume_ids': [(0, 0, self.get_vol(nfe))]})

    #     # account_move_dict.update({'l10n_br_edi_payment_method': nfe.NFe.pag.detPag[0].tPag 
    #     #                                                 if hasattr(nfe.NFe, 'pag') and hasattr(nfe.NFe.pag, 'detPag') and len(nfe.NFe.pag.detPag) > 0 
    #     #                                                 else '99'}).zfill(2)

    #     _logger.warning(f">>>>> ALLSS > import_nfe 🟢 str(nfe.NFe.pag.detPag[0].tPag {str(nfe.NFe.infNFe.pag.detPag[0].tPag)}")
    #     account_move_dict.update({
    #         'l10n_br_edi_payment_method': str(
    #             nfe.NFe.infNFe.pag.detPag[0].tPag
    #             if hasattr(nfe.NFe.infNFe, 'pag')
    #             and hasattr(nfe.NFe.infNFe.pag, 'detPag')
    #             and len(nfe.NFe.infNFe.pag.detPag) > 0
    #             else '99'
    #         ).zfill(2)
    #     })

    #     account_move_dict.update(self.get_cobr_dup(nfe))
    #     account_move_dict.update(self.get_det_pag(nfe))
    #     account_move_dict.pop('destinatary', False)
    #     if account_move_dict.get('fiscal_position_id') \
    #             and not isinstance(account_move_dict.get('fiscal_position_id'), int):
    #         account_move_dict['fiscal_position_id'] = account_move_dict.get('fiscal_position_id').id

    #     _logger.warning(f">>>>> ALLSS > import_nfe > account_move_dict para o create de account.move ({type(account_move_dict)}): {account_move_dict}")
    #     account_move = self.sudo().create(account_move_dict)
    #     _logger.warning(f">>>>> ALLSS > import_nfe > account_move ({type(account_move)}): {account_move}")
    #     return account_move
    

    

    def action_post(self):
        self = self.sudo().with_company(self.company_id)
        if self.l10n_br_allss_nf_status == "imported" and self.move_type == 'out_invoice':
            move_lines = []
            for line in self.invoice_line_ids:
                move_lines_values = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_uom_id.id,
                } 
                move_lines.append((0, 0, move_lines_values))
            
            location_dest_id = self.partner_id.property_stock_customer.id or \
                self.l10n_br_allss_picking_type_id.default_location_dest_id.id
            
            if not self.l10n_br_allss_picking_type_id:
                raise UserError('Atenção! O tipo de Operação não está definido!')
            else:
                picking = {               
                    'partner_id': self.partner_id.id,
                    'location_id': self.l10n_br_allss_picking_type_id.default_location_src_id.id,  
                    'location_dest_id': location_dest_id,
                    'picking_type_id': self.l10n_br_allss_picking_type_id.id,
                    'move_ids': move_lines,
                    'origin': self.name,
                    'l10n_br_allss_account_move_id': self.id,
                }
                stock_picking = self.env['stock.picking'].sudo().with_company(self.company_id).sudo().create(picking)                
                stock_picking.action_confirm()
                stock_picking.action_assign()

                for move in stock_picking.move_ids:
                    self.env['stock.move.line'].sudo().create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'qty_done': move.product_uom_qty,
                        'location_id': stock_picking.location_id.id,
                        'location_dest_id': stock_picking.location_dest_id.id,
                        'picking_id': stock_picking.id,
                    })

                # for line in self.invoice_line_ids:
                #     analytic_account = line.analytic_distribution and list(line.analytic_distribution.keys())[0] or False
                #     for move_line in stock_picking.move_line_ids_without_package:
                #         if analytic_account:
                #             move_line._allss_analytic_account_id = int(analytic_account)

                
                stock_picking.button_validate()
                self._compute_picking()

        return super().action_post()
    

    # def l10n_br_allss_action_view_picking(self):
    #     """ This function returns an action that display existing picking orders of given purchase order ids. When only one found, show the picking immediately.
    #     """
    #     action = self.env.ref('stock.action_picking_tree_all')
    #     result = action.read()[0]
    #     # override the context to get rid of the default filtering on operation type
    #     result['context'] = {}
    #     pick_ids = self.mapped('l10n_br_allss_picking_ids')
    #     # choose the view_mode accordingly
    #     if not pick_ids or len(pick_ids) > 1:
    #         result['domain'] = "[('id','in',%s)]" % (pick_ids.ids)
    #     elif len(pick_ids) == 1:
    #         res = self.env.ref('stock.view_picking_form', False)
    #         form_view = [(res and res.id or False, 'form')]
    #         if 'views' in result:
    #             result['views'] = form_view + [(state,view) for state,view in result['views'] if view != 'form']
    #         else:
    #             result['views'] = form_view
    #         result['res_id'] = pick_ids.id
    #     return result


    
    def _allss_get_next_code(self):
        """
        Método resonsável por gerar o próximo código para a conta contábil baseado no dado do
        prefixo do grupo de conta fornecido por contexto
        """
        _logger.warning(f"Contexto atual:{self.env.context}")

        code_prefix = self.env.context.get('l10n_br_allss_group_id').code_prefix_start
        if not code_prefix.endswith('.'):
            code_prefix += '.'
        obj_account_account = self.env.get('account.account')
        account_id = obj_account_account.search(
            [('code', 'like', ('%s%%' % code_prefix))], order='code desc', limit=1)
        if not account_id:
            return code_prefix + '1'.zfill(6)
        next_code = int(account_id.code.split('.')[-1])
        next_code += 1
        return code_prefix + str(next_code).zfill(6)


    def _allss_get_account_receivable(self, partner_name):
        """
        Método responsável por criar/encontrar a conta contábil de acordo com o nome do parceiro e
        grupo contábil fornecido por contexto
        :param partner_name: nome do parceiro
        :type partner_name: str
        :return: nova instância do objeto 'account.account'
        :rtype: object
        """
        _logger.warning(f">> CHEGOU _allss_get_account_receivable ")
        _logger.warning(f"Contexto _allss_get_account_receivable:{self.env.context}")
        obj_account_account = self.env.get('account.account')
        code = self._allss_get_next_code()
        group_id = self.env.context.get('l10n_br_allss_group_id').id
        account_ids = obj_account_account.search(
            [('name', 'ilike', partner_name), ('group_id', '=', group_id)])
        partner_ids = self.env.get('res.partner').search(
            [('property_account_receivable_id', 'in', account_ids.ids)])
        account_id = obj_account_account
        if not partner_ids and account_ids:
            account_id = account_ids[0]
        elif partner_ids and account_ids:
            account_id = account_ids.filtered(
                lambda a: a.id not in partner_ids.mapped('property_account_receivable_id').ids)
            if account_id:
                account_id = account_id[0]
        if not account_id:
            account_id = obj_account_account.sudo().create({
                'name': partner_name,
                'code': code,
                'group_id': group_id,
                'account_type': "asset_receivable",
                'reconcile': True,
            })
        return account_id.id

    def _create_partner(self, tag_nfe, destinatary):
        res = super()._create_partner(tag_nfe, destinatary)

        res.sudo().write({
            'property_account_receivable_id': self._allss_get_account_receivable(res.name)})

        return res
