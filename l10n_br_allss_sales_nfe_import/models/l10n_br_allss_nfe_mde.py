# -*- coding: utf-8 -*-

import base64
import logging
from datetime import datetime
from odoo import models
from odoo import api
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from ..service.mde import exec_download_nfe
from ..service.mde import send_event
import gzip
import io
from lxml import objectify
import re

_logger = logging.getLogger(__name__)


def convert(obj, conversion=None):
    if conversion:
        return conversion(obj)
    if isinstance(obj, objectify.StringElement):
        return str(obj)
    if isinstance(obj, objectify.IntElement):
        return int(obj)
    if isinstance(obj, objectify.FloatElement):
        return float(obj)
    raise "Tipo não implementado %s" % str(type(obj))


def get(obj, path, conversion=None):
    paths = path.split(".")
    index = 0
    for item in paths:
        if hasattr(obj, item):
            obj = obj[item]
            index += 1
        else:
            return None
    if len(paths) == index:
        return convert(obj, conversion=conversion)
    return None


def cnpj_cpf_format(cnpj_cpf):
    if len(cnpj_cpf) == 14:
        cnpj_cpf = (cnpj_cpf[0:2] + '.' + cnpj_cpf[2:5] +
                    '.' + cnpj_cpf[5:8] +
                    '/' + cnpj_cpf[8:12] +
                    '-' + cnpj_cpf[12:14])
    else:
        cnpj_cpf = (cnpj_cpf[0:3] + '.' + cnpj_cpf[3:6] +
                    '.' + cnpj_cpf[6:9] + '-' + cnpj_cpf[9:11])
    return cnpj_cpf


class L10nBrAllssNfeMde(models.Model):
    _name = 'l10n.br.allss.nfe.mde'
    _description = "Manifesto do Destinatário da NF-e"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mail.bot']
    _rec_name = 'l10n_br_allss_sequence_number'
    _order = 'l10n_br_allss_sequence_number desc'

    @api.depends('l10n_br_allss_nfe_number', 'l10n_br_allss_country_registry_vendor',
                 'l10n_br_allss_corporate_name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "NFº: {0} ({1}): {2}".format(
                rec.l10n_br_allss_nfe_number, rec.l10n_br_allss_country_registry_vendor,
                rec.l10n_br_allss_corporate_name)

    def _l10n_br_allss_default_company(self):
        return self.env.company.sudo()

    def _l10n_br_allss_compute_total_edocs(self):
        for item in self:
            item.l10n_br_allss_total_edocs = self.env['account.move'].sudo().search_count(
                [('l10n_br_allss_nfe_mde_id', '=', item.id)])

    company_id = fields.Many2one('res.company', 
                                 string="Empresa",
                                 default=_l10n_br_allss_default_company, 
                                 readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id',
                                  string=u'Moeda', 
                                  readonly=True)
    l10n_br_allss_nfe_key = fields.Char(string="Chave de Acesso", 
                                        size=50, 
                                        readonly=True)
    l10n_br_allss_nfe_number = fields.Char(string="Número NF-e", 
                                           size=10, 
                                           readonly=True)
    l10n_br_allss_sequence_number = fields.Char(string="Sequencial", 
                                                readonly=True, 
                                                size=20)
    l10n_br_allss_country_registry_vendor = fields.Char(string="CNPJ", 
                                                        readonly=True, 
                                                        size=20)
    l10n_br_allss_state_registry = fields.Char(string="RG/IE", 
                                               readonly=True, 
                                               size=20)
    l10n_br_allss_corporate_name = fields.Char(string="Razão Social", 
                                               readonly=True, 
                                               size=200)
    partner_id = fields.Many2one('res.partner', 
                                 string=u'Fornecedor',
                                 tracking=True)
    l10n_br_allss_emission_date = fields.Datetime(string="Data Emissão", 
                                                  readonly=True)
    l10n_br_allss_operation_type = fields.Selection(
                                                    [('0', 'Entrada'), 
                                                     ('1', 'Saída')],
                                                    string="Tipo de Operação", 
                                                    readonly=True)
    l10n_br_allss_nfe_price_total = fields.Float(string="Valor Total NF-e", 
                                                 readonly=True, 
                                                 digits=(18, 2))
    l10n_br_allss_nfe_situation = fields.Selection(
                                                    [('1', 'Autorizada'), 
                                                    ('2', 'Cancelada'), 
                                                    ('3', 'Denegada')],
                                                    string="Situação da NF-e", 
                                                    readonly=True)
    state = fields.Selection(string="Situação da Manifestação", 
                             readonly=True,
                             selection=[
                                 ('pendente', 'Pendente'),
                                 ('ciente', 'Ciente da operação'),
                                 ('confirmado', 'Confirmada operação'),
                                 ('desconhecido', 'Desconhecimento'),
                                 ('nao_realizado', 'Não realizado')
                             ])
    l10n_br_allss_include_type = fields.Char(string="Forma de Inclusão", 
                                             readonly=True)
    l10n_br_allss_include_date = fields.Datetime(string="Data de Inclusão", 
                                                 readonly=True)
    l10n_br_allss_nfe_xml = fields.Binary(string="Xml NF-e", 
                                          readonly=True)
    l10n_br_allss_nfe_xml_name = fields.Char(string="Nome Xml da NFe", 
                                             size=100, 
                                             readonly=True)
    l10n_br_allss_is_processed = fields.Boolean(string="Processado?", 
                                                default=False)
    l10n_br_allss_is_imported = fields.Boolean(string="Importado?", 
                                               default=False)
    l10n_br_allss_total_edocs = fields.Integer(string="Total NF-e",
                                               compute=_l10n_br_allss_compute_total_edocs)
    l10n_br_allss_account_move_id = fields.Many2one('account.move', 
                                                    string='Fatura', 
                                                    readonly=True)
    l10n_br_allss_partner_nf_empenho = fields.Char( string="NF Empenho", 
                                                    help='Número da Nota Fiscal de Empenho informado pelo Remetente.', 
                                                    readonly=True, 
                                                    copy=False)
    l10n_br_allss_xpedcom = fields.Char(string="Nº Pedido de Compras", 
                                        help='Número do Pedido de Compras do Destinatário informado pelo Remetente.', 
                                        readonly=True,
                                        copy=False)
    l10n_br_allss_xcontractcom = fields.Char(string="Nº Contrato de Compras", 
                                             help='Número do Contrato de Compra do Destinatário informado pelo Remetente.', 
                                             readonly=True, 
                                             copy=False)
    l10n_br_allss_nfe_mde_item_ids = fields.One2many(
        'l10n.br.allss.nfe.mde.item', 'l10n_br_allss_nfe_mde_id', 'Itens do MDE')


    @api.onchange('partner_id')
    def onchange_partner_id_to_update_l10n_br_allss_purchase_order_id(self):
        for item in self.l10n_br_allss_nfe_mde_item_ids:
            item.l10n_br_allss_purchase_order_id = False
            item.l10n_br_allss_purchase_order_line_id = False


    @api.constrains('l10n_br_allss_country_registry_vendor', 'partner_id')
    def _l10n_br_allss_check_partner_id(self):
        if self.partner_id and self.l10n_br_allss_country_registry_vendor != \
                self.partner_id.vat:
            raise ValidationError(
                "O Parceiro não possui o mesmo CNPJ/CPF do manifesto atual")


    def l10n_br_allss_action_view_edocs(self):
        if self.l10n_br_allss_total_edocs == 1:
            _, view_id = self.env['ir.model.data'].sudo()._xmlid_to_res_model_res_id(
                'account.view_move_form')
            vals = self.env['ir.actions.act_window'].sudo()._for_xml_id(
                'account.action_move_in_invoice_type')
            # todo: view de sped?
            vals['view_id'] = (view_id, 'sped.eletronic.doc.form')
            vals['views'][1] = (view_id, 'form')
            vals['views'] = [vals['views'][1], vals['views'][0]]
            edoc = self.env['account.move'].sudo().search(
                [('l10n_br_allss_nfe_mde_id', '=', self.id)], limit=1)
            vals['res_id'] = edoc.id
            return vals
        else:
            vals = self.env['ir.actions.act_window'].sudo()._for_xml_id(
                'account.action_move_in_invoice_type')
            vals['domain'] = [('l10n_br_allss_nfe_mde_id', '=', self.id)]
            return vals


    def _l10n_br_allss_needaction_domain_get(self):
        return [('state', '=', 'pendente')]


    def _l10n_br_allss_create_attachment(self, event, result):
        file_name = 'evento-manifesto-%s.xml' % datetime.now().strftime(
            '%Y-%m-%d-%H-%M')
        self.env['ir.attachment'].sudo().create(
            {
                'name': file_name,
                'datas': base64.b64encode(result['file_returned']),
                'description': 'Evento Manifesto Destinatário',
                'res_model': 'l10n_br_account.document_event',
                'res_id': event.id
            })


    def l10n_br_allss_action_known_emission(self):
        if self.state != 'pendente':
            return True
        evento = {
            'tpEvento': 210210,
            'descEvento': 'Ciencia da Operacao',
        }
        ms = self.env['ir.config_parameter'].sudo().get_param('l10n_br_allss_nfe_import.l10n_br_allss_ms_code_for_nfe_import')
        _logger.warning(f">>>>>>>>>> ALLSS > l10n_br_allss_action_known_emission > ms ({type(ms)}): {ms}")
        if not ms:
            _logger.warning(f">>>>>>>>>> ALLSS > l10n_br_allss_action_known_emission > raise 1: [DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!")
            raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
        ms = self.env['l10n.br.allss.ms.line'].browse(int(ms))
        if not ms:
            _logger.warning(f">>>>>>>>>> ALLSS > l10n_br_allss_action_known_emission > raise 2: [DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!")
            raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
        env_type = 1 if ms.get_ms_env() == 'producao' else 2
        _logger.warning(f">>>>>>>>>> ALLSS > l10n_br_allss_action_known_emission > env_type ({type(env_type)}): {env_type}")
        nfe_result = send_event(
            self.company_id.sudo(), self.l10n_br_allss_nfe_key, 'ciencia_operacao', self.id,
            evento=evento, env_type=env_type)

        _logger.warning(f">>>>>>>>>> ALLSS > l10n_br_allss_action_known_emission > nfe_result ({type(nfe_result)}): {nfe_result}")
        if nfe_result['code'] == 135:
            self.state = 'ciente'
        elif nfe_result['code'] == 573:
            self.state = 'ciente'
            self.sudo().message_post(body='Ciência da operação já previamente realizada')
        else:
            self.sudo().message_post(
                body='Download do xml não foi possível: %s - %s' % (
                    nfe_result['code'], nfe_result['message']
                ))
            return False

        return True


    def l10n_br_allss_action_confirm_operation(self):
        evento = {
            'tpEvento': 210200,
            'descEvento': u'Confirmacao da Operacao',
        }
        ms = self.env['ir.config_parameter'].sudo().get_param('l10n_br_allss_nfe_import.l10n_br_allss_ms_code_for_nfe_import')
        if not ms:
            raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
        ms = self.env['l10n.br.allss.ms.line'].browse(int(ms))
        if not ms:
            raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
        env_type = 1 if ms.get_ms_env() == 'producao' else 2
        nfe_result = send_event(
            self.company_id.sudo(), self.l10n_br_allss_nfe_key, 'confirma_operacao', self.id,
            evento=evento, env_type=env_type)

        if nfe_result['code'] == 135:
            self.state = 'confirmado'
        elif nfe_result['code'] == 573:
            self.state = 'confirmado'
            self.sudo().message_post(body='Confirmação da operação já previamente realizada')

        return True


    def l10n_br_allss_action_unknown_operation(self):
        evento = {
            'tpEvento': 210220,
            'descEvento': u'Desconhecimento da Operacao',
        }
        ms = self.env['ir.config_parameter'].sudo().get_param('l10n_br_allss_nfe_import.l10n_br_allss_ms_code_for_nfe_import')
        if not ms:
            raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
        ms = self.env['l10n.br.allss.ms.line'].browse(int(ms))
        if not ms:
            raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
        env_type = 1 if ms.get_ms_env() == 'producao' else 2
        nfe_result = send_event(
            self.company_id.sudo(), self.l10n_br_allss_nfe_key, 'desconhece_operacao',
            self.id, evento=evento, env_type=env_type)

        if nfe_result['code'] == 135:
            self.state = 'desconhecido'
        elif nfe_result['code'] == 573:
            self.state = 'desconhecido'
            self.sudo().message_post(body='Desconhecimento da operação já previamente realizado')

        return True


    def l10n_br_allss_action_not_operation(self, context=None, justification=None):
        evento = {
            'tpEvento': 210240,
            'descEvento': u'Operacao nao Realizada',
        }
        if not justification:
            return {
                'name': 'Operação Não Realizada',
                'type': 'ir.actions.act_window',
                'res_model': 'l10n.br.allss.wizard.operation.not.perfomed',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
            }
        ms = self.env['ir.config_parameter'].sudo().get_param('l10n_br_allss_nfe_import.l10n_br_allss_ms_code_for_nfe_import')
        if not ms:
            raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
        ms = self.env['l10n.br.allss.ms.line'].browse(int(ms))
        if not ms:
            raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
        env_type = 1 if ms.get_ms_env() == 'producao' else 2
        nfe_result = send_event(
            self.company_id.sudo(), self.l10n_br_allss_nfe_key, 'nao_realizar_operacao',
            self.id, evento=evento, justificativa=justification,
            env_type=env_type)

        if nfe_result['code'] == 135:
            self.state = 'nao_realizado'
        elif nfe_result['code'] == 573:
            self.state = 'nao_realizado'
            self.sudo().message_post(body='Tentativa de Operação não realizada ja previamente realizada')

        return True


    def l10n_br_allss_action_download_xml(self):
        ms = self.env['ir.config_parameter'].sudo().get_param('l10n_br_allss_nfe_import.l10n_br_allss_ms_code_for_nfe_import')
        if not ms:
            raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
        ms = self.env['l10n.br.allss.ms.line'].browse(int(ms))
        if not ms:
            raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
        env_type = 1 if ms.get_ms_env() == 'producao' else 2
        nfe_result = exec_download_nfe(self.company_id.sudo(), 
                                       [self.l10n_br_allss_nfe_key],
                                       env_type=env_type)
        _logger.warning(f'>>>>>>>>>> ALLSS > DF-e > l10n_br_allss_action_download_xml > nfe_result ({type(nfe_result)}): {nfe_result}')
        if nfe_result['code'] == 138:
            file_name = 'NFe%08d.xml' % int(self.l10n_br_allss_nfe_key[25:34])
            retorno = nfe_result['object']
            _logger.warning(f'>>>>>>>>>> ALLSS > DF-e > l10n_br_allss_action_download_xml > retorno ({type(retorno)}): {retorno}')
            orig_file_desc = gzip.GzipFile(
                mode='r',
                fileobj=io.BytesIO(
                    base64.b64decode(str(retorno.loteDistDFeInt.docZip)))
            )

            orig_file_cont = orig_file_desc.read()
            orig_file_desc.close()

            _logger.warning(f'>>>>>>>>>> ALLSS > DF-e > l10n_br_allss_action_download_xml > orig_file_cont ({type(orig_file_cont)}): {orig_file_cont}')
            
            if orig_file_cont:
                record = {}
                try:
                    record = {
                        'l10n_br_allss_nfe_xml': base64.encodebytes(orig_file_cont),
                        'l10n_br_allss_nfe_xml_name': file_name,
                    }
                    nfe = objectify.fromstring(orig_file_cont)
                    _logger.warning(f'>>>>>>>>>> ALLSS > DF-e > l10n_br_allss_action_download_xml > nfe ({type(nfe)}): {nfe}')
                    _logger.warning(f'>>>>>>>>>> ALLSS > DF-e > l10n_br_allss_action_download_xml > nfe.NFe.infNFe.ide.nNF ({type(nfe.NFe.infNFe.ide.nNF)}): {nfe.NFe.infNFe.ide.nNF}')
                    record.update(self.env['account.move'].sudo().get_compra(nfe))      # Retornará as seguintes informações a partir do arquivo XML baixado: l10n_br_allss_partner_nf_empenho, l10n_br_allss_xpedcom e l10n_br_allss_xcontractcom
                    record.update(self.l10n_br_allss_get_items(
                        nfe, self.partner_id.id,
                        self.env.company.l10n_br_allss_fiscal_position_id_automation.id))
                    _logger.warning(f'>>>>>>>>>> ALLSS > DF-e > l10n_br_allss_action_download_xml > record ({type(record)}): {record}')
                except AttributeError:
                    record = {
                        'l10n_br_allss_nfe_xml': base64.encodebytes(orig_file_cont),
                        'l10n_br_allss_nfe_xml_name': file_name,
                    }
                finally:
                    record and self.sudo().write(record)
                    return True
            else:
                self.sudo().message_post(
                    body='Download do xml não foi possível - Erro desconhecido')
        else:
            self.sudo().message_post(
                body='Download do xml não foi possível: %s - %s' % (
                    nfe_result['code'], nfe_result['message']
                ))
        return False


    def l10n_br_allss_action_import_xml(self, auto=False):
        self = self.with_context(allss_nfe_import=True)
        for item in self:
            if not item.l10n_br_allss_nfe_xml:
                # item.sudo().message_post(body='Faça o download do xml antes de importar!')
                if auto:
                    _logger.warning(f'>>>>> ALLSS > NF-e Import > Faça o download do xml antes de importar!')
                    return False
                else:
                    raise UserError('Faça o download do xml antes de importar!')
            ms = self.env['ir.config_parameter'].sudo().get_param('l10n_br_allss_nfe_import.l10n_br_allss_ms_code_for_nfe_import')
            if not ms:
                raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
            ms = self.env['l10n.br.allss.ms.line'].browse(int(ms))
            if not ms:
                raise UserError('[DF-e] Serviço da ALLSS Soluções em Sistemas para este processo não definido. Contate o administrador do sistema!!!')
            account_move = self.env['account.move'].sudo()
            nfe_xml = base64.decodebytes(item.l10n_br_allss_nfe_xml)
            nfe = objectify.fromstring(nfe_xml)
            try:
                nfe.NFe.infNFe.ide.nNF
            except:
                raise UserError('O XML não se refere a uma NF-e.')

            company = item.company_id.sudo()
            vals = {'l10n_br_allss_nfe_mde_id': item.id,
                    'l10n_br_allss_ms_code': ms.id,
                    'l10n_br_allss_nf_environment': account_move._get_nf_environment(ms),
                    }
            account_move_id = account_move.import_nfe(
                auto, company, nfe, nfe_xml, item,
                company.l10n_br_allss_partner_automation,
                company.l10n_br_allss_invoice_automation, 
                company.l10n_br_allss_tax_automation,
                company.l10n_br_allss_supplierinfo_automation, 
                fiscal_position_id=company.l10n_br_allss_fiscal_position_id_automation or False,
                account_move_dict=vals,
                purchase_order_automation=company.l10n_br_allss_purchase_order_automation
            )
            if not account_move_id:
                return False
            item.sudo().write({'l10n_br_allss_account_move_id': account_move_id.id,
                               'l10n_br_allss_is_imported': True})
        return True

    def l10n_br_allss_get_items(self, nfe, partner_id, fiscal_position_id=None):
        items = [(5, 0, 0)]
        for det in nfe.NFe.infNFe.det:
            item_data = self.l10n_br_allss_create_nfe_mde_item(
                det, partner_id, fiscal_position_id)
            items.append((0, 0, item_data))
        return {'l10n_br_allss_nfe_mde_item_ids': items}

    def l10n_br_allss_create_nfe_mde_item(self, item, partner_id, fiscal_position_id=None):
        codigo = get(item.prod, 'cProd', str)
        seller_id = self.env['product.supplierinfo'].sudo().search([
            ('partner_id', '=', partner_id),
            ('product_code', '=', codigo),
            ('product_id.active', '=', True)])

        product = None
        if seller_id:
            product = seller_id.product_id
            if len(product) > 1:
                message = '\n'.join(
                    ["Produto: %s - %s" % (x.default_code or '', x.name) for x in product])
                raise UserError("Existem produtos duplicados com mesma codificação, corrija-os "
                                "antes de prosseguir:\n%s" % message)

        if not product and item.prod.cEAN and \
                str(item.prod.cEAN) != 'SEM GTIN':
            product = self.env['product.product'].sudo().search(
                [('barcode', '=', item.prod.cEAN)], limit=1)
        if not product:
            product = self.env['product.product'].sudo().search(
                [('product_tmpl_id.default_code', '=', codigo)], limit=1)
        if not product and get(item, 'prod.nItemPed'):
            product = self.env['product.product'].sudo().search(
                [('product_tmpl_id.default_code', '=', get(item, 'prod.nItemPed'))], limit=1)

        uom = str(item.prod.uCom)

        product_id = product and product.id or False

        quantidade = item.prod.qCom
        preco_unitario = item.prod.vUnCom
        valor_bruto = item.prod.vProd
        # desconto = 0
        # if hasattr(item.prod, 'vDesc'):
        #     desconto = (item.prod.vDesc / (preco_unitario * quantidade)) * 100

        tax_ids = []
        # if hasattr(item.prod, 'vDesc'):
        #     tax_ids.append(self.l10n_br_allss_get_tax_nfe_import('DESCONTO', 0, item.prod.vDesc,
        #                                                          tax_automation))
        if hasattr(item.prod, 'vSeg'):
            tax_ids.append(self.l10n_br_allss_get_tax_id('SEGURO'))
        if hasattr(item.prod, 'vFrete'):
            tax_ids.append(self.l10n_br_allss_get_tax_id('FRETE'))
        if hasattr(item.prod, 'vOutro'):
            tax_ids.append(self.l10n_br_allss_get_tax_id('OUTROS'))
        # indicador_total = str(item.prod.indTot)
        cfop = item.prod.CFOP and item.prod.CFOP.text or ''
        cfop_id = self.env.get('l10n.br.allss.fiscal.cfop').search(
            [('l10n_br_allss_code', '=', cfop)], limit=1).id
        ncm = item.prod.NCM
        # cest = get(item, 'item.prod.CEST')
        nItemPed = get(item, 'prod.nItemPed')
        x_ped = get(item, 'prod.xPed')
        purchase_order_id = self.env.get('purchase.order').sudo().search(
            [('partner_id', '=', partner_id), ('name', '=', x_ped), ('state', '=', 'purchase')],
            limit=1)
        purchase_order_line_id = self.env.get('purchase.order.line').sudo().search(
            [('order_id', '=', purchase_order_id.id), ('sequence', '=', nItemPed)], limit=1) \
            if purchase_order_id else None

        item_ids = {
            'l10n_br_allss_product_id': product_id,
            'l10n_br_allss_xprod': item.prod.xProd or (product and product.name)
            or 'Item do arquivo XML Importado',
            'l10n_br_allss_ucom': uom,
            'l10n_br_allss_qcom': quantidade,
            'l10n_br_allss_vuncom': preco_unitario,
            'l10n_br_allss_fiscal_position_id': fiscal_position_id,
            'l10n_br_allss_cfop_id': cfop_id,
            'l10n_br_allss_ncm': ncm,
            'l10n_br_allss_cean': item.prod.cEAN,
            'l10n_br_allss_cprod': codigo,
            'l10n_br_allss_nitemped': nItemPed,
            'l10n_br_allss_xped': x_ped,
            'l10n_br_allss_vprod': valor_bruto,
            'l10n_br_allss_nitem': int(item.attrib.get('nItem')),
            'l10n_br_allss_purchase_order_id': purchase_order_id and purchase_order_id.id,
            'l10n_br_allss_purchase_order_line_id': purchase_order_line_id
            and purchase_order_line_id.id,
        }

        # IMPOSTOS
        dado_imposto_item = [(5, 0, 0)]
        obj_account_move = self.env.get('account.move')
        if hasattr(item.imposto, 'ICMS'):
            icms_dados = obj_account_move._get_icms(item.imposto)
            tax_id = self.l10n_br_allss_get_tax_id(icms_dados.get('icms_st_base_calculo')
                                                   and 'ICMSST' or 'ICMS')
            tax_ids.append(tax_id)
            tax_id and dado_imposto_item.append((0, 0, {
                'l10n_br_allss_tax_id': tax_id,
                'l10n_br_allss_base_calculo': icms_dados.get('icms_st_base_calculo')
                and (icms_dados.get('icms_st_base_calculo') or 0)
                or (icms_dados.get('icms_base_calculo') or 0),
                'l10n_br_allss_aliquota': icms_dados.get('icms_st_base_calculo')
                and (icms_dados.get('icms_st_aliquota') or 0)
                or (icms_dados.get('icms_aliquota') or 0),
                'l10n_br_allss_valor': icms_dados.get('icms_st_base_calculo')
                and (icms_dados.get('icms_st_valor') or 0)
                or (icms_dados.get('icms_valor') or 0),
                'l10n_br_allss_cst': icms_dados.get('icms_cst'),
            }))

        if hasattr(item.imposto, 'ISSQN'):
            iss_dados = obj_account_move._get_issqn(item.imposto.ISSQN)
            tax_id = self.l10n_br_allss_get_tax_id('ISS')
            tax_ids.append(tax_id)
            tax_id and dado_imposto_item.append((0, 0, {
                'l10n_br_allss_tax_id': tax_id,
                'l10n_br_allss_base_calculo': iss_dados.get('iss_base_calculo') or 0,
                'l10n_br_allss_aliquota': iss_dados.get('iss_aliquota') or 0,
                'l10n_br_allss_valor': iss_dados.get('iss_valor') or 0,
                'l10n_br_allss_cst': iss_dados.get('iss_cst') or '',
            }))

        if hasattr(item.imposto, 'IPI'):
            ipi_dados = obj_account_move._get_ipi(item.imposto.IPI)
            tax_id = self.l10n_br_allss_get_tax_id('IPI')
            tax_ids.append(tax_id)
            tax_id and dado_imposto_item.append((0, 0, {
                'l10n_br_allss_tax_id': tax_id,
                'l10n_br_allss_base_calculo': ipi_dados.get('ipi_base_calculo') or 0,
                'l10n_br_allss_aliquota': ipi_dados.get('ipi_aliquota') or 0,
                'l10n_br_allss_valor': ipi_dados.get('ipi_valor') or 0,
                'l10n_br_allss_cst': ipi_dados.get('ipi_cst') or '',
            }))

        pis_dados = obj_account_move._get_pis(item.imposto.PIS)
        tax_id = self.l10n_br_allss_get_tax_id('PIS')
        tax_ids.append(tax_id)
        tax_id and dado_imposto_item.append((0, 0, {
            'l10n_br_allss_tax_id': tax_id,
            'l10n_br_allss_base_calculo': pis_dados.get('pis_base_calculo') or 0,
            'l10n_br_allss_aliquota': pis_dados.get('pis_aliquota') or 0,
            'l10n_br_allss_valor': pis_dados.get('pis_valor') or 0,
            'l10n_br_allss_cst': pis_dados.get('pis_cst') or '',
        }))

        cofins_dados = obj_account_move._get_cofins(item.imposto.COFINS)
        tax_id = self.l10n_br_allss_get_tax_id('COFINS')
        tax_ids.append(tax_id)
        tax_id and dado_imposto_item.append((0, 0, {
            'l10n_br_allss_tax_id': tax_id,
            'l10n_br_allss_base_calculo': cofins_dados.get('cofins_base_calculo') or 0,
            'l10n_br_allss_aliquota': cofins_dados.get('cofins_aliquota') or 0,
            'l10n_br_allss_valor': cofins_dados.get('cofins_valor') or 0,
            'l10n_br_allss_cst': cofins_dados.get('cofins_cst') or '',
        }))

        if hasattr(item.imposto, 'II'):
            ii_dados = obj_account_move._get_ii(item.imposto.II)
            tax_id = self.l10n_br_allss_get_tax_id('II')
            tax_ids.append(tax_id)
            tax_id and dado_imposto_item.append((0, 0, {
                'l10n_br_allss_tax_id': tax_id,
                'l10n_br_allss_base_calculo': ii_dados.get('ii_base_calculo') or 0,
                'l10n_br_allss_aliquota': ii_dados.get('ii_aliquota') or 0,
                'l10n_br_allss_valor': ii_dados.get('ii_valor') or 0,
                'l10n_br_allss_cst': ii_dados.get('ii_cst') or '',
            }))

        if hasattr(item.imposto, 'DIFAL'):
            difal_dados = obj_account_move._get_difal(item.imposto.DIFAL)
            tax_id = self.l10n_br_allss_get_tax_id('DIFAL')
            tax_ids.append(tax_id)
            tax_id and dado_imposto_item.append((0, 0, {
                'l10n_br_allss_tax_id': tax_id,
                'l10n_br_allss_base_calculo': difal_dados.get('difal_base_calculo') or 0,
                'l10n_br_allss_aliquota': difal_dados.get('difal_aliquota') or 0,
                'l10n_br_allss_valor': difal_dados.get('difal_valor') or 0,
                'l10n_br_allss_cst': difal_dados.get('difal_cst') or '',
            }))

        if hasattr(item.imposto, 'FCP'):
            fecp_dados = obj_account_move._get_fecp(item.imposto.FCP)
            tax_id = self.l10n_br_allss_get_tax_id('FECPIC')
            tax_ids.append(tax_id)
            tax_id and dado_imposto_item.append((0, 0, {
                'l10n_br_allss_tax_id': tax_id,
                'l10n_br_allss_base_calculo': fecp_dados.get('fecp_base_calculo') or 0,
                'l10n_br_allss_aliquota': fecp_dados.get('fecp_aliquota') or 0,
                'l10n_br_allss_valor': fecp_dados.get('fecp_valor') or 0,
                'l10n_br_allss_cst': fecp_dados.get('fecp_cst') or '',
            }))

        if hasattr(item.imposto, 'AFRMM'):
            afrmm_dados = obj_account_move._get_afrmm(item.imposto.AFRMM)
            tax_id = self.l10n_br_allss_get_tax_id('AFRMM')
            tax_ids.append(tax_id)
            tax_id and dado_imposto_item.append((0, 0, {
                'l10n_br_allss_tax_id': tax_id,
                'l10n_br_allss_base_calculo': afrmm_dados.get('afrmm_base_calculo') or 0,
                'l10n_br_allss_aliquota': afrmm_dados.get('afrmm_aliquota') or 0,
                'l10n_br_allss_valor': afrmm_dados.get('afrmm_valor') or 0,
                'l10n_br_allss_cst': afrmm_dados.get('afrmm_cst') or '',
            }))

        tax_ids = list(filter(lambda l: l, tax_ids))

        item_ids.update({
            'l10n_br_allss_tax_ids': tax_ids,
            'l10n_br_allss_taxation_ids': dado_imposto_item,
        })

        return item_ids

    def l10n_br_allss_get_tax_id(self, tax_name):
        obj_ir_module_module = self.env.get('ir.module.module')
        module = 'l10n_br_allss_account_template_only_taxes'
        if not obj_ir_module_module.search_count(
                [('name', '=', module), ('state', '=', 'installed')]):
            module = 'l10n_br_allss_account_template_full'
            if not obj_ir_module_module.search_count(
                    [('name', '=', module), ('state', '=', 'installed')]):
                module = ''
        if module:
            try:
                brw_tax = self.env.ref('%s.%s_template_account_tax_%s_xmlimport' % (
                    module, self.env.company.id, tax_name.lower()))
            except ValueError:
                brw_tax = None
            if brw_tax:
                return brw_tax.id
        obj_account_tax = self.env.get('account.tax')
        obj_allss_account_tax = self.env.get('l10n.br.allss.account.tax')
        tax_registration_id = self.env.get('l10n.br.allss.tax.registration').sudo().search(
            [('l10n_br_allss_code', '=', tax_name.upper())])
        if not tax_registration_id:
            return
        allss_account_tax_id = obj_allss_account_tax.search([
            ('l10n_br_allss_tax_registration_id', '=', tax_registration_id.id)
        ], limit=1)
        # amount_type = 'percent'
        # if tax_name.upper() in ('DESCONTO', 'FRETE', 'SEGURO', 'OUTROS'):
        #     amount_type = 'fixed'
        # if tax_name.upper() in ('ICMS', 'PIS', 'COFINS'):
        #     amount_type = 'division'
        tax_ids = obj_account_tax.search([
            ('l10n_br_allss_account_tax_id', 'in', allss_account_tax_id.ids),
            # ('amount_type', '=', amount_type),
            ('type_tax_use', '=', 'purchase')
        ], limit=1)
        return tax_ids and tax_ids.ids[0] or None

    def _search(self, domain, offset=0, limit=None, order=None):
        if not domain:
            domain = []
        domain.append(['company_id', '=', self.env.company.id])
        res = super(L10nBrAllssNfeMde, self)._search(domain, offset, limit, order)
        return res
