# -*- coding: utf-8 -*-
# © 2023 Tiago Prates <tiago.prates@allss.com.br>, ALLSS Soluções em Sistemas LTDA
# © 2023 Anderson Coelho <anderson.coelho@allss.com.br>, ALLSS Soluções em Sistemas LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import re
import base64
import pytz
import logging
from odoo import fields, models, _
from dateutil import parser
from datetime import datetime
from lxml import objectify
from odoo.exceptions import UserError, ValidationError
from odoo import api
from contextlib import contextmanager


_logger = logging.getLogger(__name__)


def convert(obj, conversion=None):
    if conversion:
        return conversion(obj.text)
    if isinstance(obj, objectify.StringElement):
        return str(obj)
    if isinstance(obj, objectify.IntElement):
        return int(obj)
    if isinstance(obj, objectify.FloatElement):
        return float(obj)
    raise u"Tipo não implementado %s" % str(type(obj))


def get(obj, path, conversion=None):
    paths = path.split(".")
    index = 0
    for item in paths:
        if not item:
            continue
        if hasattr(obj, item):
            obj = obj[item]
            index += 1
        else:
            return None
    if len(paths) == index:
        return convert(obj, conversion=conversion)
    return None


def remove_none_values(dict):
    res = {}
    res.update({k: v for k, v in dict.items() if v})
    return res


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


def format_ncm(ncm):
    if len(ncm) == 4:
        ncm = ncm[:2] + '.' + ncm[2:4]
    elif len(ncm) == 6:
        ncm = ncm[:4] + '.' + ncm[4:6]
    else:
        ncm = ncm[:4] + '.' + ncm[4:6] + '.' + ncm[6:8]

    return ncm


class AllssAccountMoveNfeImport(models.Model):
    _inherit = 'account.move'

    # state = fields.Selection(selection_add=[('imported', 'Importado')],
    #                          ondelete={'imported': 'cascade'})
    l10n_br_allss_nfe_mde_id = fields.Many2one(
        'l10n.br.allss.nfe.mde', string="Manifesto Eletrônico", readonly=True)
    l10n_br_allss_nfe_xml_portions_data = fields.Text('NF-e XML Portions')

    def get_ide(self, nfe, operacao, fiscal_position_id):
        """
        Importa a seção <ide> do xml
        :param nfe:
        :param operacao:
        :param fiscal_position_id:
        :return:
        """
        ide = nfe.NFe.infNFe.ide
        modelo = ide.mod or '55'
        serie = ide.serie
        num_controle = ide.cNF
        numero_nfe = ide.nNF
        data_emissao = parser.parse(str(ide.dhEmi))
        dt_entrada_saida = get(ide, 'dhSaiEnt')
        natureza_operacao = ide.natOp
        fpos = self.env.get('fiscal.position')
        
        _logger.warning(f'>>>>>>>>>> ALLSS > get_ide > operacao ({type(operacao)}): {operacao}')
        _logger.warning(f'>>>>>>>>>> ALLSS > get_ide > natureza_operacao ({type(natureza_operacao)}): {natureza_operacao}')
        _logger.warning(f'>>>>>>>>>> ALLSS > get_ide > fiscal_position_id ({type(fiscal_position_id)}): {fiscal_position_id}')
        
        if not fpos:
            fpos = self.env['account.fiscal.position'].sudo().search([
                                    ('l10n_br_allss_fiscal_type', '=', 'entrada' if operacao in ('in_invoice','out_refund', 'in_receipt') else 'saida'),
                                    ('l10n_br_allss_operation_description', 'ilike', natureza_operacao)
                                ], limit=1)
        if not fpos:
            fpos = self.env['account.fiscal.position'].sudo().search([
                                    ('l10n_br_allss_fiscal_type', '=', 'entrada' if operacao in ('in_invoice','out_refund', 'in_receipt') else 'saida'),
                                    ('name', 'ilike', natureza_operacao)
                                ], limit=1)
        if not fpos:
            fpos = fiscal_position_id

        if dt_entrada_saida:
            dt_entrada_saida = parser.parse(str(dt_entrada_saida))
            dt_entrada_saida = dt_entrada_saida.astimezone(pytz.utc).replace(tzinfo=None)
        indicador_destinatario = ide.idDest
        ambiente = 'Homologação' if ide.tpAmb == 2 \
            else 'Produção'
        finalidade_emissao = str(ide.finNFe)
        if finalidade_emissao == '1':
            finalidade_emissao = 'normal'
        elif finalidade_emissao == '2':
            finalidade_emissao = 'other_complement'
        elif finalidade_emissao == '3':
            # todo: atribuí 'Não aplicável' para a finalidade de ajuste (3) pois não há opção
            #  compatível
            finalidade_emissao = 'not_applicable'
        else:
            finalidade_emissao = 'devolution'
        serie = self.env.get('l10n.br.allss.nf.series').sudo().search(
            [('l10n_br_allss_code', '=', serie),
             ('l10n_br_allss_fiscal_type', '=', 'product')],
            limit=1)

        doc_type = (
                    serie.sudo().l10n_br_allss_latam_document_type_id
                    or self.env.ref(
                        f"l10n_br.dt_{modelo or '55'}",
                        raise_if_not_found=False,
                    )
                )

        return dict(
            move_type=operacao,
            # model='nfce' if str(modelo) == '65' else 'nfe',
            l10n_br_allss_nf_series=serie.id,
            l10n_br_allss_control_number=num_controle,
            name=numero_nfe,
            l10n_br_allss_nf_number=numero_nfe,
            invoice_date=data_emissao.astimezone(pytz.utc).replace(tzinfo=None),
            l10n_br_allss_nf_send_date=dt_entrada_saida,
            # l10n_br_allss_ms_code=self.env.get('l10n.br.allss.ms.line').sudo().search(
            #     [('l10n_br_allss_env_type', '=', ambiente)], limit=1),
            l10n_br_allss_doc_type=finalidade_emissao,
            state='draft',
            l10n_br_allss_nf_status='imported',
            # name='Documento Eletrônico: n° ' + str(numero_nfe),
            l10n_br_allss_operation_description=natureza_operacao,
            fiscal_position_id=fpos,
            l10n_latam_document_type_id=doc_type.id if doc_type else False,
        )

    def get_partner_nfe(self, nfe, destinatary, partner_automation, dfe):
        """Importação da sessão <emit> do xml"""
        if dfe and dfe.partner_id:
            return dict(partner_id=dfe.partner_id.id)
        tag_nfe = None
        if destinatary:
            tag_nfe = nfe.NFe.infNFe.emit
        else:
            tag_nfe = nfe.NFe.infNFe.dest

        if hasattr(tag_nfe, 'CNPJ'):
            cnpj_cpf = cnpj_cpf_format(str(tag_nfe.CNPJ.text).zfill(14))
        else:
            cnpj_cpf = cnpj_cpf_format(str(tag_nfe.CPF.text).zfill(11))

        partner_id = self.env['res.partner'].sudo().search([
            ('vat', '=', cnpj_cpf)], limit=1)
        if not partner_id:
            if partner_automation:
                partner_id = self._create_partner(tag_nfe, destinatary)
            elif not partner_id and not partner_automation:
                raise UserError((
                        'Parceiro não cadastrado. Selecione a opção cadastrar ' +
                        'parceiro, ou realize o cadastro manualmente.'))
        if partner_id and dfe and not dfe.partner_id:
            dfe.sudo().write({'partner_id': partner_id.id})

        return dict(partner_id=partner_id.id)

    def get_ICMSTot(self, nfe):
        ICMSTot = nfe.NFe.infNFe.total.ICMSTot
        return dict(
            valor_bc_icms=get(ICMSTot, 'vBC'),
            valor_icms=get(ICMSTot, 'vICMS'),
            valor_icms_deson=get(ICMSTot, 'vICMSDeson'),
            valor_bc_icmsst=get(ICMSTot, 'vBCST'),
            valor_icmsst=get(ICMSTot, 'vST'),
            valor_bruto=get(ICMSTot, 'vProd'),
            valor_produtos=get(ICMSTot, 'vProd'),
            valor_frete=get(ICMSTot, 'vFrete'),
            valor_seguro=get(ICMSTot, 'vSeg'),
            valor_desconto=get(ICMSTot, 'vDesc'),
            valor_ii=get(ICMSTot, 'vII'),
            valor_ipi=get(ICMSTot, 'vIPI'),
            pis_valor=get(ICMSTot, 'vPIS'),
            cofins_valor=get(ICMSTot, 'vCOFINS'),
            valor_final=get(ICMSTot, 'vNF'),
            valor_estimado_tributos=get(ICMSTot, 'vTotTrib'),
            # vOutro=ICMSTot.vOutro,
        )

    def get_retTrib(self, nfe):
        retTrib = nfe.NFe.infNFe.total.retTrib
        return dict(
            valor_retencao_pis=retTrib.vRetPIS,
            valor_retencao_cofins=retTrib.vRetCOFINS,
            valor_retencao_csll=retTrib.vRetCSLL,
            valor_retencao_irrf=retTrib.vIRRF,
            valor_retencao_previdencia=retTrib.vRetPrev
            # vBCIRRF=retTrib.vBCIRRF,
            # vBCRetPrev=retTrib.vBCRetPrev,
        )

    def get_transp(self, nfe):
        transportadora = {}

        if hasattr(nfe.NFe.infNFe, 'transp'):
            transp = nfe.NFe.infNFe.transp

            if transp.modFrete == 9:
                return transportadora

            if hasattr(transp, 'transporta'):
                cnpj_cpf = get(transp, 'transporta.CNPJ', str)

                if cnpj_cpf:
                    cnpj_cpf = cnpj_cpf_format(str(cnpj_cpf).zfill(14))

                state_obj = self.env.get('res.country.state')
                vehicle_transp_state_id = state_obj.search([
                    ('code', '=', get(transp, 'veicTransp.UF')),
                    ('country_id.code', '=', 'BR')], limit=1)

                transportadora_id = self.env['res.partner'].sudo().search([
                    ('vat', '=', cnpj_cpf)], limit=1)

                if not transportadora_id:
                    state_id = state_obj.search([
                        ('code', '=', get(transp, 'transporta.UF')),
                        ('country_id.code', '=', 'BR')], limit=1)
                    city_id = self.env.get('res.city').sudo().search([
                        ('name', 'ilike', get(transp, 'transporta.xMun')),
                        ('state_id', '=', state_id.id),
                        ('country_id.code', '=', 'BR'),
                    ], limit=1)
                    vals = {
                        'vat': cnpj_cpf,
                        'name': get(transp, 'transporta.xNome') or 'Transportadora',
                        'l10n_br_allss_state_registry_ids': [
                            (0, 0, {'l10n_br_allss_code': get(transp, 'transporta.IE', str),
                                    'l10n_br_allss_state_id': state_id.id,
                                    'active_registry': True,
                                    'l10n_br_allss_sequence': 0})
                            ] if get(transp, 'transporta.IE', str) 
                                and len(transp.transporta.IE.text) > 1 
                              else [],
                        'street_name': get(transp, 'transporta.xEnder'),
                        'city': get(transp, 'transporta.xMun') or city_id.name,
                        'city_id': city_id.id,
                        'state_id': state_id.id,
                        'l10n_br_allss_corporate_name': get(transp, 'transporta.xNome'),
                        'company_type': 'company',
                        'is_company': True,
                        'company_id': None,
                    }
                    transportadora_id = self.env['res.partner'].sudo().create(vals)

                transportadora.update({
                    'l10n_br_allss_shipping_company': transportadora_id.id,
                    'l10n_br_allss_license_plate': get(transp, 'veicTransp.placa'),
                    'l10n_br_allss_uf_vehicle': vehicle_transp_state_id.id or None,
                    'l10n_br_allss_rntc': get(transp, 'veicTransp.RNTC'),
                })

        return transportadora and [(0, 0, transportadora)] or []

    def get_reboque(self, nfe):
        if hasattr(nfe.NFe.infNFe.transp, 'reboque'):
            reboque = nfe.NFe.infNFe.transp.reboque

            reboque_ids = {
                'l10n_br_allss_ferry': get(reboque, '.balsa'),
                'l10n_br_allss_uf_vehicle': get(reboque, '.UF'),
                'l10n_br_allss_wagon': get(reboque, '.vagao'),
                'l10n_br_allss_rntc': get(reboque, '.RNTC'),
                'l10n_br_allss_license_plate': get(reboque, '.placa'),
            }

            reboque_ids = remove_none_values(reboque_ids)
            return [(0, 0, reboque_ids)]

        return []

    def get_vol(self, nfe):
        if hasattr(nfe.NFe.infNFe.transp, 'vol'):
            vol = nfe.NFe.infNFe.transp.vol
            volume_ids = {
                'l10n_br_allss_kind': get(vol, 'esp'),
                'l10n_br_allss_volume_qty': get(vol, 'qVol'),
                'l10n_br_allss_numbering': get(vol, 'nVol'),
                'l10n_br_allss_net_weight': get(vol, 'pesoL'),
                'l10n_br_allss_gross_weight': get(vol, 'pesoB'),
                'l10n_br_allss_brand': get(vol, 'marca'),
            }

            return remove_none_values(volume_ids)

        return {}

    def get_cobr_fat(self, nfe):
        if hasattr(nfe.NFe.infNFe, 'cobr'):
            cobr = nfe.NFe.infNFe.cobr

            if hasattr(cobr, 'fat'):
                fatura = {
                    'numero_fatura': get(cobr, 'fat.nFat', str),
                    'fatura_bruto': get(cobr, 'fat.vOrig'),
                    'fatura_desconto': get(cobr, 'fat.vDesc'),
                    'fatura_liquido': get(cobr, 'fat.vLiq'),
                }
                return fatura

        return {}

    def get_cobr_dup(self, nfe):
        if hasattr(nfe.NFe.infNFe, 'cobr'):
            cobr = nfe.NFe.infNFe.cobr

            if len(cobr) and hasattr(cobr, 'dup'):
                duplicatas = []
                for dup in cobr.dup:
                    duplicata = {
                        'date_maturity': get(dup, 'dVenc'),
                        'price_total': dup.vDup,
                        'amount_currency': dup.vDup,
                        'l10n_br_allss_duplicate_number': get(dup, 'nDup'),
                    }
                    duplicatas.append(remove_none_values(duplicata))

                return {'l10n_br_allss_nfe_xml_portions_data': str(duplicatas)}
        return {}

    def get_det_pag(self, nfe):
        if hasattr(nfe.NFe.infNFe, 'pag'):
            pag = nfe.NFe.infNFe.pag

            if len(pag) and hasattr(pag, 'detPag'):
                if hasattr(pag.detPag, 'card'):
                    cnpj_cpf = None
                    if hasattr(pag.detPag.card, 'CNPJ'):
                        cnpj_cpf = cnpj_cpf_format(str(pag.detPag.card.CNPJ.text).zfill(14))
                    elif hasattr(pag.detPag.card, 'CPF'):
                        cnpj_cpf = cnpj_cpf_format(str(pag.detPag.card.CPF.text).zfill(11))
                    return {'l10n_br_allss_partner_contact_id': cnpj_cpf and self.env.get(
                        'res.partner').search([('vat', '=', cnpj_cpf)], limit=1).id or None}

        return {}

    def get_protNFe(self, nfe, company_id):
        protNFe = nfe.protNFe.infProt

        if protNFe.cStat in [100, 150] or \
                protNFe.cStat == 110 and company_id.vat in protNFe.chNFe:
            authorization_date = nfe.protNFe.infProt.dhRecbto
            if authorization_date:
                authorization_date = parser.parse(str(authorization_date))
                authorization_date = authorization_date.astimezone(pytz.utc).replace(tzinfo=None)
            return dict(
                l10n_br_allss_nf_key=protNFe.chNFe,
                l10n_br_allss_authorization_date=authorization_date,
                l10n_br_allss_return_message=protNFe.xMotivo,
                # l10n_br_allss_number_protocol=protNFe.nProt,            ### ToDo, O campo l10n_br_allss_number_protocol poderá ser eliminado futuramente, passando a valer apenas o l10n_br_allss_verify_code
                l10n_br_allss_verify_code=protNFe.nProt,
                l10n_br_allss_return_code=protNFe.cStat,
            )

    def get_infAdic(self, nfe):
        info_adicionais = {
            'l10n_br_allss_message_for_tax_authority': get(
                nfe, 'NFe.infNFe.infAdic.infAdFisco'),
            'l10n_br_allss_message_for_customer': get(
                nfe, 'NFe.infNFe.infAdic.infCpl'),
        }

        return info_adicionais

    def get_main(self, nfe):
        return dict(
            invoice_payment_term_id=self.invoice_payment_term_id.id,
            fiscal_position_id=self.fiscal_position_id,
        )

    def create_account_move_line(self, item, company_id, partner_id, supplier_automation,
                                 tax_automation, fiscal_position_id=None, account_move_dict=None):
        codigo = get(item.prod, 'cProd', str)
        seller_id = self.env['product.supplierinfo'].sudo().search([
            ('partner_id', '=', partner_id),
            ('product_code', '=', codigo),
            ('product_id.active', '=', True)])

        nfe_mde_item = account_move_dict and self.env.get('l10n.br.allss.nfe.mde').browse(
            account_move_dict.get('l10n_br_allss_nfe_mde_id')).l10n_br_allss_nfe_mde_item_ids.\
            filtered(lambda i: i.l10n_br_allss_nitem == int(item.attrib.get('nItem'))) or None
        product = nfe_mde_item and nfe_mde_item.l10n_br_allss_product_id or None
        fiscal_position_id = (nfe_mde_item and nfe_mde_item.l10n_br_allss_fiscal_position_id) or fiscal_position_id
        if not fiscal_position_id:
            raise ValidationError('Cadastre a "Posição Fiscal" nas definições da empresa, aba '
                                  '"Informações Gerais", seção "NF-e Automation."')
        operation = self.env.get('account.fiscal.position').sudo().browse(fiscal_position_id.id).\
            l10n_br_allss_operation_id or False
        nfe_mde_product_name = product and product.name
        if seller_id and not product:
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

        uom_id = self.env['uom.uom'].sudo().search([
            ('name', '=ilike', str(item.prod.uCom))], limit=1).id

        if not product and supplier_automation:
            product = self._create_product(partner_id, item.prod, uom_id)

        product_id = product and product.id or False
        # if not uom_id:
        #     uom_id = product and product.uom_id.id or False
        if product.uom_po_id or product.uom_id:
            uom_id = product.uom_po_id.id or product.uom_id.id

        quantidade = item.prod.qCom
        preco_unitario = item.prod.vUnCom
        # valor_bruto = item.prod.vProd
        perc_desconto = 0
        vr_desconto = 0
        if hasattr(item.prod, 'vDesc'):
            perc_desconto = (item.prod.vDesc / (preco_unitario * quantidade)) * 100
            vr_desconto = float(item.prod.vDesc)

        tax_ids = []
        # if hasattr(item.prod, 'vDesc'):
        #     tax_ids.append(self.l10n_br_allss_get_tax_nfe_import('DESCONTO', 0, item.prod.vDesc,
        #                                                          tax_automation))
        if hasattr(item.prod, 'vSeg'):
            tax_ids.append(self.l10n_br_allss_get_tax_nfe_import('SEGURO', 0, item.prod.vSeg,
                                                                 tax_automation))
        if hasattr(item.prod, 'vFrete'):
            tax_ids.append(self.l10n_br_allss_get_tax_nfe_import('FRETE', 0, item.prod.vFrete,
                                                                 tax_automation))
        if hasattr(item.prod, 'vOutro'):
            tax_ids.append(self.l10n_br_allss_get_tax_nfe_import('OUTROS', 0, item.prod.vOutro,
                                                                 tax_automation))
        indicador_total = str(item.prod.indTot)
        # cfop = re.sub('.','',str(item.prod.CFOP.text))
        cfop = (nfe_mde_item and nfe_mde_item.l10n_br_allss_cfop_id.l10n_br_allss_code) or (item.prod.CFOP and item.prod.CFOP.text) or ''
        _logger.warning(f">>>>>>>>>> ALLSS > create_account_move_line > cfop ({type(cfop)}): {cfop}")
        cfop_id = self.env.get('l10n.br.allss.fiscal.cfop').sudo().search(
                [('l10n_br_allss_reverse_cfop_code', '=', cfop)], limit=1)
        _logger.warning(f">>>>>>>>>> ALLSS > create_account_move_line > cfop_id ({type(cfop_id)}): {cfop_id}")
        if not cfop_id:
            cfop = (re.sub('5','1',re.sub('6','2',re.sub('7','3',cfop[:1]))) + cfop[1:])
            cfop_id = self.env.get('l10n.br.allss.fiscal.cfop').sudo().search(
                    [('l10n_br_allss_code', '=', cfop)], limit=1)
            _logger.warning(f">>>>>>>>>> ALLSS > create_account_move_line > cfop 2 ({type(cfop)}): {cfop}")
            _logger.warning(f">>>>>>>>>> ALLSS > create_account_move_line > cfop_id 2 ({type(cfop_id)}): {cfop_id}")
        if not cfop_id and fiscal_position_id and fiscal_position_id.l10n_br_allss_cfop_id:
            cfop_id = fiscal_position_id.l10n_br_allss_cfop_id
        if cfop_id and cfop_id.l10n_br_allss_operation_id:
            operation = cfop_id.l10n_br_allss_operation_id
        # ncm = item.prod.NCM
        # cest = get(item, 'item.prod.CEST')
        nItemPed = nfe_mde_item and nfe_mde_item.l10n_br_allss_nitemped \
            or get(item, 'prod.nItemPed')
        x_ped = nfe_mde_item and nfe_mde_item.l10n_br_allss_xped \
            or get(item, 'prod.xPed')

        account_move_line = {
            'product_id': product_id,
            'name': nfe_mde_product_name or item.prod.xProd or (product and product.name)
            or 'Item do arquivo XML Importado',
            'product_uom_id': uom_id,
            'quantity': quantidade,
            'price_unit': preco_unitario,
            # 'valor_bruto': valor_bruto,
            'discount': perc_desconto,
            # 'seguro': seguro,
            # 'frete': frete,
            # 'outras_despesas': outras_despesas,
            # 'valor_liquido': valor_bruto - perc_desconto + frete + seguro + outras_despesas,
            # 'indicador_total': indicador_total,
            'l10n_br_allss_fiscal_position_id': fiscal_position_id.id,
            'l10n_br_allss_cfop_id': cfop_id.id,
            # 'ncm': ncm,
            'l10n_br_allss_product_ean': item.prod.cEAN,
            'l10n_br_allss_product_cprod': codigo,
            'l10n_br_allss_product_xprod': item.prod.xProd,

            # 'cest': cest,
            'l10n_br_allss_xitempedcom': nItemPed,
            'l10n_br_allss_xpedcom': x_ped,
            'company_id': company_id.id,
        }

        icms_dados = {}
        icms_aliquota = 0
        icms_valor = 0
        icms_subs_aliquota = 0
        icms_st_ret_aliquota = 0
        icms_base_calculo = 0
        icms_subs_valor = 0
        icms_st_ret_valor = 0
        icms_tax_id = None
        if hasattr(item.imposto, 'ICMS'):
            icms_dados = self._get_icms(item.imposto)
            icms_aliquota = icms_dados.get('icms_st_base_calculo') \
                and (icms_dados.get('icms_st_aliquota') or 0) \
                or (icms_dados.get('icms_aliquota') or 0) \
                or (icms_dados.get('icms_aliquota_credito') or 0)
            icms_valor = icms_dados.get('icms_st_base_calculo') \
                and (icms_dados.get('icms_st_valor') or 0) \
                or (icms_dados.get('icms_valor') or 0) \
                or (icms_dados.get('icms_valor_credito') or 0)
            icms_desonerado = icms_dados.get('icms_valor_desonerado') or 0
            if icms_desonerado:
                icms_aliquota = round(icms_desonerado / item.prod.vProd, 2) * 100
                icms_valor = icms_desonerado
            lista_icms = ['ICMS']
            if icms_dados.get('icms_st_base_calculo'):
                lista_icms = ['ICMSST']
            if icms_dados.get('icms_st_base_calculo_ret'):
                lista_icms = ['ICMSSubstituto', 'ICMSSTRet']
            for cod_icms in lista_icms if icms_dados else []:
                icms_aliquota_escolhida = icms_aliquota
                icms_valor_escolhido = icms_valor
                if 'ICMSSubstituto' == cod_icms:
                    icms_aliquota_escolhida = round(
                        (icms_dados.get('icms_st_valor_substituto') * icms_dados.get(
                            'icms_st_aliquota_consumidor_final')
                         ) / (
                            icms_dados.get('icms_st_valor_substituto') + icms_dados.get(
                                'icms_st_valor_ret')
                        ), 2)
                    icms_subs_aliquota = icms_aliquota_escolhida
                    icms_subs_valor = icms_dados.get('icms_st_valor_substituto') or 0
                    icms_valor_escolhido = icms_subs_valor
                if 'ICMSSTRet' == cod_icms:
                    icms_aliquota_escolhida = round(
                        (icms_dados.get('icms_st_valor_ret') * icms_dados.get(
                            'icms_st_aliquota_consumidor_final')
                         ) / (
                            icms_dados.get('icms_st_valor_substituto') + icms_dados.get(
                                'icms_st_valor_ret')
                        ), 2)
                    icms_st_ret_aliquota = icms_aliquota_escolhida
                    icms_st_ret_valor = icms_dados.get('icms_st_valor_ret') or 0
                    icms_valor_escolhido = icms_st_ret_valor
                icms_tax_id = self.l10n_br_allss_get_tax_nfe_import(
                    cod_icms,
                    icms_aliquota_escolhida,
                    icms_valor_escolhido,
                    tax_automation,
                    **{'icms_st_aliquota_mva': icms_dados.get('icms_st_aliquota_mva'),
                       'icms_aliquota_reducao_base': icms_dados.get('icms_aliquota_reducao_base'),
                       'cst': icms_dados.get('icms_cst'),
                       'motivo_desoneracao': icms_dados.get('icms_motivo_desoneracao'),
                       'origem': icms_dados.get('origem'),
                       }
                )
                tax_ids.append(icms_tax_id)
            icms_base_calculo = icms_dados.get('icms_st_base_calculo') \
                or icms_dados.get('icms_base_calculo') or item.prod.vProd or 0
            if icms_dados.get('icms_st_base_calculo_ret'):
                icms_base_calculo = icms_dados.get('icms_st_base_calculo_ret')
            # account_move_line.sudo().update()
        if icms_dados.get('origem') and product:
            product.l10n_br_allss_origin_id = self.env.get('l10n.br.allss.product.origin').sudo().search(
                [('l10n_br_allss_code', '=', icms_dados.get('origem'))], limit=1).id or None


        iss_dados = {}
        if hasattr(item.imposto, 'ISSQN'):
            iss_dados = self._get_issqn(item.imposto.ISSQN)
            iss_dados and tax_ids.append(self.l10n_br_allss_get_tax_nfe_import(
                'ISS', iss_dados.get('iss_aliquota') or 0, iss_dados.get('iss_valor') or 0,
                tax_automation))
            # account_move_line.sudo().update()

        # nome_produto = get(item.prod, 'xProd') or 'Produto criado através da importação do arquivo XML da NF-e.'
        ipi_dados = {}

        if hasattr(item.imposto, 'IPI'):
            ipi_dados = self._get_ipi(item.imposto.IPI)
            ipi_dados and tax_ids.append(self.l10n_br_allss_get_tax_nfe_import(
                'IPI', ipi_dados.get('ipi_aliquota') or 0, ipi_dados.get('ipi_valor') or 0,
                tax_automation, cst=ipi_dados.get('ipi_cst')))
            # account_move_line.sudo().update()

        pis_dados = self._get_pis(item.imposto.PIS)
        pis_dados and tax_ids.append(self.l10n_br_allss_get_tax_nfe_import(
            'PIS', pis_dados.get('pis_aliquota') or 0, pis_dados.get('pis_valor') or 0,
            tax_automation, cst=pis_dados.get('pis_cst')))
        # account_move_line.sudo().update()

        cofins_dados = self._get_cofins(item.imposto.COFINS)
        cofins_dados and tax_ids.append(self.l10n_br_allss_get_tax_nfe_import(
            'COFINS', cofins_dados.get('cofins_aliquota') or 0, pis_dados.get('cofins_valor') or 0,
            tax_automation, cst=cofins_dados.get('cofins_cst')))
        # account_move_line.sudo().update()

        ii_dados = {}
        if hasattr(item.imposto, 'II'):
            ii_dados = self._get_ii(item.imposto.II)
            ii_dados and tax_ids.append(self.l10n_br_allss_get_tax_nfe_import(
                'II', 0, ii_dados.get('ii_valor') or 0, tax_automation))
            # account_move_line.sudo().update()

        difal_dados = {}
        if hasattr(item.imposto, 'ICMSUFDest') and icms_dados:
            difal_dados = self._get_difal(icms_dados)
            difal_dados and tax_ids.append(self.l10n_br_allss_get_tax_nfe_import(
                'DIFAL', difal_dados.get('difal_aliquota'), difal_dados.get('difal_valor'),
                tax_automation, icms_inter_tax_id=icms_tax_id))

        fecp_dados = {}
        if hasattr(item.imposto, 'FCP'):
            fecp_dados = self._get_fecp(item.imposto.FCP)
            fecp_dados and tax_ids.append(self.l10n_br_allss_get_tax_nfe_import(
                'FECPIC', fecp_dados.get('fecp_base_calculo') or 0,
                fecp_dados.get('fecp_valor') or 0, tax_automation))

        afrmm_dados = {}
        if hasattr(item.imposto, 'AFRMM'):
            afrmm_dados = self._get_afrmm(item.imposto.AFRMM)
            afrmm_dados and tax_ids.append(self.l10n_br_allss_get_tax_nfe_import(
                'AFRMM', 0, afrmm_dados.get('afrmm_valor') or 0, tax_automation))

        tax_ids = list(filter(lambda l: l, tax_ids))

        account_move_line.update({
            'tax_ids': tax_ids,
            'l10n_br_allss_import_nfe_tax': str({
                'vr_desconto': vr_desconto,
                'icms': {
                    'base_calculo': icms_base_calculo,
                    'aliquota': icms_aliquota,
                    'valor': icms_valor,
                    'cst': icms_dados.get('icms_cst'),
                    'aliquota_icms_subs': icms_subs_aliquota,
                    'aliquota_icms_st_ret': icms_st_ret_aliquota,
                    'valor_icms_subs': icms_subs_valor,
                    'valor_icms_st_ret': icms_st_ret_valor,
                },
                'pis': {
                    'base_calculo': pis_dados.get('pis_base_calculo') or 0,
                    'aliquota': pis_dados.get('pis_aliquota') or 0,
                    'valor': pis_dados.get('pis_valor') or 0,
                    'cst': pis_dados.get('pis_cst'),
                },
                'cofins': {
                    'base_calculo': cofins_dados.get('cofins_base_calculo') or 0,
                    'aliquota': cofins_dados.get('cofins_aliquota') or 0,
                    'valor': cofins_dados.get('cofins_valor') or 0,
                    'cst': cofins_dados.get('cofins_cst'),
                },
                'ipi': {
                    'base_calculo': ipi_dados.get('ipi_base_calculo') or 0,
                    'aliquota': ipi_dados.get('ipi_aliquota') or 0,
                    'valor': ipi_dados.get('ipi_valor') or 0,
                    'cst': ipi_dados.get('ipi_cst'),
                },
                'ii': {
                    'base_calculo': ii_dados.get('ii_base_calculo') or 0,
                    'aliquota': ii_dados.get('ii_aliquota') or 0,
                    'valor': ii_dados.get('ii_valor') or 0,
                    'cst': ii_dados.get('ii_cst'),
                },
                'difal': {
                    'base_calculo': difal_dados.get('difal_base_calculo') or 0,
                    'aliquota': difal_dados.get('difal_aliquota') and difal_dados.get(
                        'difal_aliquota') - icms_aliquota or 0,
                    'valor': difal_dados.get('difal_valor') or 0,
                    'cst': difal_dados.get('difal_cst'),
                },
                'fecpic': {
                    'base_calculo': fecp_dados.get('fecp_base_calculo') or 0,
                    'aliquota': fecp_dados.get('fecp_aliquota') or 0,
                    'valor': fecp_dados.get('fecp_valor') or 0,
                    'cst': fecp_dados.get('fecp_cst'),
                },
                'afrmm': {
                    'base_calculo': afrmm_dados.get('afrmm_base_calculo') or 0,
                    'aliquota': afrmm_dados.get('afrmm_aliquota') or 0,
                    'valor': afrmm_dados.get('afrmm_valor') or 0,
                    'cst': afrmm_dados.get('afrmm_cst'),
                },
            }),
        })

        if hasattr(item.prod, 'DI'):
            di_ids = []
            for di in item.prod.DI:
                di_ids.append(self._get_di(item.prod.DI))
            account_move_line.update({'l10n_br_allss_import_declaration_ids': di_ids})

        _logger.warning(f">>>>>>>>>> ALLSS > create_account_move_line > account_move_line ({type(account_move_line)}): {account_move_line}")
        _logger.warning(f">>>>>>>>>> ALLSS > create_account_move_line > operation ({type(operation)}): {operation}")

        return [account_move_line, operation]

    def l10n_br_allss_get_tax_nfe_import(self, tax_name, tax_aliquot, tax_value, tax_automation,
                                         **kwargs):
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
                return 4, brw_tax.id, False
        obj_allss_account_tax = self.env.get('l10n.br.allss.account.tax')
        obj_cst = self.env.get('l10n.br.allss.cst')
        tax_registration_id = self.env.get('l10n.br.allss.tax.registration').sudo().search(
            [
                '|',
                ('l10n_br_allss_code', '=', tax_name.upper()),
                ('l10n_br_allss_code', '=', tax_name)
            ])
        if not tax_registration_id:
            return []
        args_allss_account_tax = [
            ('l10n_br_allss_tax_registration_id', '=', tax_registration_id.id),
            ('l10n_br_allss_cst_id.l10n_br_allss_cst', '=', kwargs.get('cst'))
        ]
        reason_exemption_id = False
        if kwargs.get('motivo_desoneracao'):
            reason_exemption_id = self.env.get('l10n.br.allss.reason.exemption').search(
                [('l10n_br_allss_code', '=', kwargs.get('motivo_desoneracao'))], limit=1).id
            args_allss_account_tax.append(
                ('l10n_br_allss_reason_exemption_id', '=', reason_exemption_id))
        allss_account_tax_id = obj_allss_account_tax.search(args_allss_account_tax, limit=1)
        cst_id = False
        if tax_registration_id and tax_automation and kwargs.get('cst'):
            cst_id = obj_cst.search(
                [('l10n_br_allss_tax_registration_id', '=', tax_registration_id.id),
                ('l10n_br_allss_cst', '=', kwargs.get('cst'))], limit=1)
            if not cst_id:
                cst_id = obj_cst.sudo().create({
                    'l10n_br_allss_tax_registration_id': tax_registration_id.id,
                        'l10n_br_allss_cst': kwargs.get('cst'),
                        'name': tax_name + ' ' + kwargs.get('cst')
                    })
        if not allss_account_tax_id and tax_automation:
            allss_account_tax_id = obj_allss_account_tax.sudo().create(
                {'name': tax_name, 
                 'l10n_br_allss_tax_registration_id': tax_registration_id.id,
                 'l10n_br_allss_cst_id': cst_id.id if cst_id else False,
                 'l10n_br_allss_reason_exemption_id': reason_exemption_id,
                 'l10n_br_allss_modBC_id': kwargs.get('origem') and self.env.get(
                     'l10n.br.allss.modbc').search(
                     [('l10n_br_allss_code', '=', kwargs.get('origem')),
                      ('l10n_br_allss_tax_registration_id', '=', tax_registration_id.id),
                      ], limit=1).id or False,
                 })
        if allss_account_tax_id and tax_automation and kwargs.get('cst') and not allss_account_tax_id.l10n_br_allss_cst_id:
            allss_account_tax_id.l10n_br_allss_cst_id = cst_id
        amount_type = 'percent'
        price_include = False
        if tax_name.upper() in ('DESCONTO', 'FRETE', 'SEGURO', 'OUTROS'):
            amount_type = 'fixed'
        if tax_name.upper() in ('ICMS', 'PIS', 'COFINS', 'ICMSSUBSTITUTO', 'ICMSSTRET', 'DIFAL'):
            amount_type = 'division'
            price_include = 'tax_included'
        if amount_type != 'fixed':
            tax_name += ' %s%% Importado NF-e' % tax_aliquot
        if len(kwargs.get('cst') or '') == 3:
            tax_name += ' SN'
        
        tax_dict = {
                # 'name': tax_name,
                'l10n_br_allss_account_tax_id': allss_account_tax_id.ids[0],
                'amount_type': amount_type,
                'type_tax_use': 'purchase',
                'amount_mva': kwargs.get('icms_st_aliquota_mva') or 0,
                'base_reduction': kwargs.get('icms_aliquota_reducao_base') or 0,
                # 'l10n_br_allss_tax_rate_compute': amount_type != 'fixed' and not tax_aliquot,
                'l10n_br_allss_tax_rate_compute': False,
                'amount': amount_type == 'fixed' and tax_value or tax_aliquot,
                'price_include_override': price_include,
                # 'description': tax_name,
                # 'tax_group_id': tax_group_id,
            }

        ret_get_tax = self._get_tax(
                            tax_name,
                            allss_account_tax_id,
                            tax_dict,
                            tax_automation,
                            **kwargs
                        )
        if ret_get_tax:
            tax_ids = ret_get_tax[0]
            message = ret_get_tax[1]
            if message:
                _logger.warning(f">>>>>>>>>> ALLSS > l10n_br_allss_get_tax_nfe_import > message: {message}")

        # tax_ids = obj_account_tax.search([
        #     ('l10n_br_allss_account_tax_id', 'in', allss_account_tax_id.ids),
        #     ('amount_type', '=', amount_type),
        #     ('amount', '=', amount_type == 'fixed' and tax_value or tax_aliquot),
        #     ('type_tax_use', '=', 'purchase'),
        #     ('company_id', '=', self.env.company.id)
        # ], limit=1)
        # if not tax_ids and tax_automation:
        #     tax_group_id = obj_account_tax_group.search([('name', '=', tax_name)], limit=1).id
        #     if not tax_group_id:
        #         tax_group_id = obj_account_tax_group.sudo().create({'name': tax_name}).id
        #     if obj_account_tax.search([('name', '=', tax_name)]):
        #         tax_name += '*'
        #     tax_ids = obj_account_tax.sudo().create({
        #         'name': tax_name,
        #         'l10n_br_allss_account_tax_id': allss_account_tax_id.ids[0],
        #         'amount_type': amount_type,
        #         'type_tax_use': 'purchase',
        #         'amount_mva': kwargs.get('icms_st_aliquota_mva') or 0,
        #         'base_reduction': kwargs.get('icms_aliquota_reducao_base') or 0,
        #         # 'l10n_br_allss_tax_rate_compute': amount_type != 'fixed' and not tax_aliquot,
        #         'l10n_br_allss_tax_rate_compute': False,
        #         'amount': amount_type == 'fixed' and tax_value or tax_aliquot,
        #         'price_include_override': price_include,
        #         'description': tax_name,
        #         'tax_group_id': tax_group_id,
        #     })
        # tax_ids and tax_automation and allss_account_tax_id.ids \
        #     and kwargs.get('icms_inter_tax_id') \
        #     and allss_account_tax_id[0].write(
        #         {'l10n_br_allss_tax_deduce_result': [(6, 0, [kwargs.get('icms_inter_tax_id')[1]])]}
        #     )
        return tax_ids and (4, tax_ids.ids[0], False) or []

    def _get_icms(self, imposto):
        csts = ['00', '10', '20', '30', '40', '41', '50',
                '51', '60', '70', '90']
        csts += ['101', '102', '103', '201', '202', '203',
                 '300', '400', '500', '900']

        cst_item = None
        vals = {}

        for cst in csts:
            tag_icms = None
            if hasattr(imposto.ICMS, 'ICMSSN%s' % cst):
                tag_icms = 'ICMSSN'
                cst_item = get(imposto, 'ICMS.ICMSSN%s.CSOSN' % cst, str)
            elif hasattr(imposto.ICMS, 'ICMS%s' % cst):
                tag_icms = 'ICMS'
                cst_item = get(imposto, 'ICMS.ICMS%s.CST' % cst, str)
                cst_item = str(cst_item).zfill(2)
            if tag_icms:
                icms = imposto.ICMS
                vals = {
                    'icms_cst': cst_item,
                    'origem': get(
                        icms, '%s%s.orig' % (tag_icms, cst), str),
                    'icms_tipo_base': get(
                        icms, '%s%s.modBC' % (tag_icms, cst), str),
                    'icms_aliquota_diferimento': get(
                        icms, '%s%s.pDif' % (tag_icms, cst)),
                    'icms_valor_diferido': get(
                        icms, '%s%s.vICMSDif' % (tag_icms, cst)),
                    'icms_motivo_desoneracao': get(
                        icms, '%s%s.motDesICMS' % (tag_icms, cst)),
                    'icms_valor_desonerado': get(
                        icms, '%s%s.vICMSDeson' % (tag_icms, cst)),
                    'icms_base_calculo': get(
                        icms, '%s%s.vBC' % (tag_icms, cst)),
                    'icms_aliquota_reducao_base': get(
                        icms, '%s%s.pRedBC' % (tag_icms, cst)),
                    'icms_aliquota': get(
                        icms, '%s%s.pICMS' % (tag_icms, cst)),
                    'icms_valor': get(
                        icms, '%s%s.vICMS' % (tag_icms, cst)),
                    'icms_aliquota_credito': get(
                        icms, '%s%s.pCredSN' % (tag_icms, cst)),
                    'icms_valor_credito': get(
                        icms, '%s%s.vCredICMSSN' % (tag_icms, cst)),
                    'icms_st_tipo_base': get(
                        icms, '%s%s.modBCST' % (tag_icms, cst), str),
                    'icms_st_aliquota_mva': get(
                        icms, '%s%s.pMVAST' % (tag_icms, cst)),
                    'icms_st_base_calculo': get(
                        icms, '%s%s.vBCST' % (tag_icms, cst)),
                    'icms_st_aliquota_reducao_base': get(
                        icms, '%s%s.pRedBCST' % (tag_icms, cst)),
                    'icms_st_aliquota': get(
                        icms, '%s%s.pICMSST' % (tag_icms, cst)),
                    'icms_st_valor': get(
                        icms, '%s%s.vICMSST' % (tag_icms, cst)),
                    'icms_st_base_calculo_ret': get(
                        icms, '%s%s.vBCSTRet' % (tag_icms, cst)),
                    'icms_st_aliquota_consumidor_final': get(
                        icms, '%s%s.pST' % (tag_icms, cst)),
                    'icms_st_valor_substituto': get(
                        icms, '%s%s.vICMSSubstituto' % (tag_icms, cst)),
                    'icms_st_valor_ret': get(
                        icms, '%s%s.vICMSSTRet' % (tag_icms, cst)),
                    'icms_bc_uf_dest': get(
                        imposto, 'ICMSUFDest.vBCUFDest'),
                    'icms_bc_fcp_uf_dest': get(
                        imposto, 'ICMSUFDest.vBCFCPUFDest'),
                    'icms_aliquota_fcp_uf_dest': get(
                        imposto, 'ICMSUFDest.pFCPUFDest'),
                    'icms_aliquota_uf_dest': get(
                        imposto, 'ICMSUFDest.pICMSUFDest'),
                    'icms_aliquota_interestadual': get(
                        imposto, 'ICMSUFDest.pICMSInter'),
                    'icms_aliquota_inter_part': get(
                        imposto, 'ICMSUFDest.pICMSInterPart'),
                    'icms_fcp_uf_dest': get(
                        imposto, 'ICMSUFDest.vFCPUFDest'),
                    'icms_uf_dest': get(
                        imposto, 'ICMSUFDest.vICMSUFDest'),
                    'icms_uf_remet': get(
                        imposto, 'ICMSUFDest.vICMSUFRemet'),
                }

        return remove_none_values(vals)

    def _get_issqn(self, issqn):
        vals = {
            'item_lista_servico': get(issqn, 'cListServ'),
            'iss_aliquota': get(issqn, 'vAliq'),
            'iss_base_calculo': get(issqn, 'vBC'),
            'iss_valor': get(issqn, 'vISSQN'),
            'iss_valor_retencao': get(issqn, 'vISSRet'),
        }
        return remove_none_values(vals)

    def _get_ipi(self, ipi):
        classe_enquadramento_ipi = get(ipi, 'clEnq')
        codigo_enquadramento_ipi = get(ipi, 'cEnq')

        vals = {}
        for item in ipi.getchildren():
            ipi_cst = get(ipi, '%s.CST' % item.tag[36:])
            ipi_cst = str(ipi_cst).zfill(2)
            ipi_valor = get(ipi, '%s.vIPI' % item.tag[36:]) or 0
            # if not ipi_valor:
            #     continue

            vals = {
                'ipi_cst': ipi_cst,
                'ipi_base_calculo': get(ipi, '%s.vBC' % item.tag[36:]),
                'ipi_aliquota': get(ipi, '%s.pIPI' % item.tag[36:]),
                'ipi_valor': ipi_valor or 0,
                'classe_enquadramento_ipi': classe_enquadramento_ipi,
                'codigo_enquadramento_ipi': codigo_enquadramento_ipi,
            }

        return remove_none_values(vals)

    def _get_pis(self, pis):
        vals = {}
        for item in pis.getchildren():
            pis_cst = get(pis, '%s.CST' % item.tag[36:])
            pis_cst = str(pis_cst).zfill(2)

            vals = {
                'pis_cst': pis_cst,
                'pis_base_calculo': get(pis, '%s.vBC' % item.tag[36:]),
                'pis_aliquota': get(pis, '%s.pPIS' % item.tag[36:]),
                'pis_valor': get(pis, '%s.vPIS' % item.tag[36:]),
            }

        return remove_none_values(vals)

    def _get_cofins(self, cofins):
        vals = {}
        for item in cofins.getchildren():
            cofins_cst = get(cofins, '%s.CST' % item.tag[36:])
            cofins_cst = str(cofins_cst).zfill(2)

            vals = {
                'cofins_cst': cofins_cst,
                'cofins_base_calculo': get(cofins, '%s.vBC' % item.tag[36:]),
                'cofins_aliquota': get(cofins, '%s.pCOFINS' % item.tag[36:]),
                'cofins_valor': get(cofins, '%s.vCOFINS' % item.tag[36:]),
            }

        return remove_none_values(vals)

    def _get_ii(self, ii):
        vals = {
            'ii_base_calculo': get(ii, 'vBC'),
            'ii_valor_despesas': get(ii, 'vDespAdu'),
            'ii_valor_iof': get(ii, 'vIOF'),
            'ii_valor': get(ii, 'vII'),
        }
        return remove_none_values(vals)

    def _get_di(self, di):
        state_code = get(di, 'UFDesemb')
        state_id = self.env['res.country.state'].sudo().search([
            ('code', '=', state_code),
            ('country_id.code', '=', 'BR')
        ])
        vals = {
            'name': get(di, 'nDI'),
            'l10n_br_allss_date_registration': get(di, 'dDI'),
            'l10n_br_allss_location': get(di, 'xLocDesemb'),
            'l10n_br_allss_state_id': state_id.id,
            'l10n_br_allss_date_release': get(di, 'dDesemb'),
            'l10n_br_allss_type_transportation': get(di, 'tpViaTransp', str),
            'l10n_br_allss_type_import': get(di, 'tpIntermedio', str),
            'l10n_br_allss_exporting_code': get(di, 'cExportador'),
            'l10n_br_allss_line_ids': []
        }

        if hasattr(di, 'adi'):
            for adi in di.adi:
                adi_vals = {
                    'l10n_br_allss_sequence': get(di.adi, 'nSeqAdic'),
                    'name': get(di.adi, 'nAdicao'),
                    'l10n_br_allss_manufacturer_code': get(di.adi, 'cFabricante'),
                }
                adi_vals = remove_none_values(adi_vals)
                adi = self.env['l10n.br.allss.nfe.import.declaration.line'].sudo().create(adi_vals)
                vals['line_ids'].append((4, adi.id, False))

        vals = remove_none_values(vals)
        di = self.env['l10n.br.allss.nfe.import.declaration'].sudo().create(vals)

        return (4, di.id, False)

    def _get_difal(self, difal):
        vals = {
            'difal_base_calculo': difal.get('icms_bc_uf_dest') or 0,
            'difal_aliquota': difal.get('icms_aliquota_uf_dest') or 0,
            'difal_valor': difal.get('icms_uf_dest') or 0,
        }
        return remove_none_values(vals)

    def _get_fecp(self, fecp):
        vals = {}
        for item in fecp.getchildren():
            fecp_cst = get(fecp, '%s.CST' % item.tag[36:])
            fecp_cst = str(fecp_cst).zfill(2)

            vals = {
                'fecp_cst': fecp_cst,
                'fecp_base_calculo': get(fecp, '%s.vBC' % item.tag[36:]),
                'fecp_aliquota': get(fecp, '%s.pFCP' % item.tag[36:]),
                'fecp_valor': get(fecp, '%s.vFCP' % item.tag[36:]),
            }
        return remove_none_values(vals)

    def _get_afrmm(self, afrmm):
        vals = {}
        for item in afrmm.getchildren():
            afrmm_cst = get(afrmm, '%s.CST' % item.tag[36:])
            afrmm_cst = str(afrmm_cst).zfill(2)

            vals = {
                'afrmm_cst': afrmm_cst,
                'afrmm_base_calculo': get(afrmm, '%s.vBC' % item.tag[36:]),
                'afrmm_aliquota': get(afrmm, '%s.pAFRMM' % item.tag[36:]),
                'afrmm_valor': get(afrmm, '%s.vAFRMM' % item.tag[36:]),
            }
        return remove_none_values(vals)

    def get_items(self, nfe, company_id, partner_id, account_move_dict, dfe,
                  supplier_automation, tax_automation, fiscal_position_id=None,
                  purchase_order_id=None, purchase_order_automation=None):
        ret = {}
        items = []
        obj_purchase_order_line = self.env.get('purchase.order.line').sudo()
        for det in nfe.NFe.infNFe.det:
            nfe_mde_item = account_move_dict and self.env.get('l10n.br.allss.nfe.mde').browse(
                account_move_dict.get('l10n_br_allss_nfe_mde_id')).l10n_br_allss_nfe_mde_item_ids. \
                filtered(lambda i: i.l10n_br_allss_nitem == int(det.attrib.get('nItem'))) or None
            _logger.warning(f'>>>>>>>>>> ALLSS > NF-e Import > get_items > det ({type(det)}): {det}')
            ret_create_account_move_line = self.create_account_move_line(
                det, company_id, partner_id, supplier_automation, tax_automation,
                fiscal_position_id=fiscal_position_id, account_move_dict=account_move_dict)
            item_dict = ret_create_account_move_line[0]
            operation = ret_create_account_move_line[1]

            _logger.warning(f'>>>>>>>>>> ALLSS > NF-e Import > get_items > purchase_order_id ({type(purchase_order_id)}): {purchase_order_id}')
            _logger.warning(f'>>>>>>>>>> ALLSS > NF-e Import > get_items > purchase_order_automation ({type(purchase_order_automation)}): {purchase_order_automation}')
            _logger.warning(f'>>>>>>>>>> ALLSS > NF-e Import > get_items > item_dict ({type(item_dict)}): {item_dict}')
            
            purchase_line_id = False
            if nfe_mde_item and nfe_mde_item.l10n_br_allss_purchase_order_id:
                item_dict.update({
                    'purchase_order_id': nfe_mde_item.l10n_br_allss_purchase_order_id.id})
                purchase_order_id = nfe_mde_item.l10n_br_allss_purchase_order_id.id
            if nfe_mde_item and nfe_mde_item.l10n_br_allss_purchase_order_line_id:
                item_dict.update({
                    'purchase_line_id': nfe_mde_item.l10n_br_allss_purchase_order_line_id.id})
                purchase_line_id = nfe_mde_item.l10n_br_allss_purchase_order_line_id
            elif purchase_order_id and item_dict.get('product_id') and not purchase_line_id:
                purchase_line_id = obj_purchase_order_line.sudo().search(
                    [('order_id', '=', purchase_order_id),
                     ('sequence', '=', item_dict.get('l10n_br_allss_xitempedcom'))], limit=1
                )
                if not purchase_line_id:
                    purchase_line_id = obj_purchase_order_line.sudo().search(
                        [('order_id', '=', purchase_order_id),
                         ('product_id', '=', item_dict.get('product_id'))], limit=1)
                if purchase_line_id:
                    item_dict.update({
                        'purchase_line_id': purchase_line_id.id,
                        'purchase_order_id': purchase_order_id
                    })
            if account_move_dict.get('move_type') == 'in_invoice' and not purchase_line_id and purchase_order_automation and item_dict.get('product_id'):
                if not purchase_order_id:
                    ret.update(self._l10n_br_allss_create_purchase_order_vals(
                        account_move_dict, dfe, nfe_mde_item and nfe_mde_item.l10n_br_allss_xped))
                    purchase_order_id = ret.get('purchase_id')
                if purchase_order_id:
                    purchase_line_vals = {
                        'order_id': purchase_order_id,
                        'product_id': item_dict.get('product_id') or False,
                        'name': item_dict.get('name') or 'Item criado a partir da importação do arquivo XML da NF-e',
                        'product_qty': item_dict.get('quantity') or 1,
                        'price_unit': item_dict.get('price_unit') or 0,
                        'product_uom': item_dict.get('product_uom_id') or False,
                        'l10n_br_allss_fiscal_position_id': item_dict.get('l10n_br_allss_fiscal_position_id') or False,
                        'l10n_br_allss_cfop_id': item_dict.get('l10n_br_allss_cfop_id') or False,
                        'taxes_id': item_dict.get('tax_ids') or False,
                        'l10n_br_allss_import_nfe_tax': item_dict.get('l10n_br_allss_import_nfe_tax') or False,
                        'date_planned': fields.Datetime.now(),
                    }
                    purchase_line_id = obj_purchase_order_line.sudo().create(purchase_line_vals)
            _logger.warning(f'>>>>>>>>>> ALLSS > NF-e Import > get_items > purchase_order_id ({type(purchase_order_id)}): {purchase_order_id}')
            _logger.warning(f'>>>>>>>>>> ALLSS > NF-e Import > get_items > purchase_line_id ({type(purchase_line_id)}): {purchase_line_id}')
            if purchase_order_id and purchase_line_id:
                item_dict.update({
                    'purchase_line_id': purchase_line_id.id,
                    'purchase_order_id': purchase_order_id
                })
            if 'l10n_br_allss_xpedcom' not in item_dict and hasattr(nfe.NFe.infNFe, 'compras'):
                item_dict.update({'l10n_br_allss_xpedcom': get(nfe.NFe.infNFe.compras, 'xPed') or False})
            items.append((0, 0, item_dict))
            ret.update({'l10n_br_allss_operation_id': operation.id, 'invoice_line_ids': items})
            _logger.warning(f'>>>>>>>>>> ALLSS > NF-e Import > get_items > ret ({type(ret)}): {ret}')
        return ret

    def get_compra(self, nfe):
        if hasattr(nfe.NFe.infNFe, 'compras'):
            compra = nfe.NFe.infNFe.compras

            # Os campos aqui retornados deverão também ser criados nas models:
            #  - 'l10n.br.allss.nfe.mde'
            #  - 'account.move'
            #  - 'pos.order'
            return {
                'l10n_br_allss_partner_nf_empenho': get(compra, 'xNEmp'),
                'l10n_br_allss_xpedcom': get(compra, 'xPed'),
                'l10n_br_allss_xcontractcom': get(compra, 'xCont'),
            }

        return {}

    def import_nfe(self, auto, company_id, nfe, nfe_xml, dfe, 
                   partner_automation=False,
                   account_invoice_automation=False, 
                   tax_automation=False,
                   supplierinfo_automation=False, 
                   fiscal_position_id=False,
                   payment_term_id=False, 
                   account_move_dict=None, 
                   purchase_order_automation=False):

        account_move_dict = account_move_dict or {}
        partner_vals = self._get_company_account_move(auto, nfe, partner_automation)
        if not partner_vals:
            return False
        _logger.warning(f">>>>> ALLSS > import_nfe > partner_vals: {partner_vals}")

        if self.existing_account_move(auto, nfe, partner_vals):
            # self.sudo().message_post(body='NF-e já importada!')
            if auto:
                _logger.warning(f'>>>>> ALLSS > NF-e Import > NF-e já importada!')
                return False
            else:
                raise UserError('NF-e já importada!')

        account_move_dict.update(self.get_compra(nfe))
        purchase_order = account_move_dict.get('l10n_br_allss_xpedcom')
        _logger.warning(f">>>>> ALLSS > import_nfe > purchase_order ({type(purchase_order)}): {purchase_order}")
        purchase_order_dict = self._l10n_br_allss_get_purchase_order_vals(purchase_order)       
        _logger.warning(f">>>>> ALLSS > import_nfe > purchase_order_dict ({type(purchase_order_dict)}): {purchase_order_dict}")

        company_id = self.env['res.company'].sudo().browse(partner_vals['company_id'])
        
        _logger.warning(f">>>>> ALLSS > import_nfe > company_id ({type(company_id)}): {company_id}")
        
        if not fiscal_position_id:
            fiscal_position_id = (purchase_order_dict and purchase_order_dict.get('fiscal_position_id')) or company_id.l10n_br_allss_fiscal_position_id_automation or False
        
        account_move_dict.update(partner_vals)
        account_move_dict.pop('destinatary')
        account_move_dict.update({
            'l10n_br_allss_nf_xml': base64.encodebytes(nfe_xml),
            'l10n_br_allss_nf_number': nfe.NFe.infNFe.ide.nNF,
            # 'name': nfe.NFe.infNFe.ide.nNF,
            'l10n_latam_document_number': nfe.NFe.infNFe.ide.nNF,
        })
        account_move_dict.update(self.get_protNFe(nfe, company_id))
        account_move_dict.update(self.get_main(nfe))
        partner = self.get_partner_nfe(
            nfe, partner_vals['destinatary'], partner_automation, dfe)
        account_move_dict.update(
            self.get_ide(nfe, partner_vals['move_type'], fiscal_position_id))
        account_move_dict.update(partner)
        if purchase_order_dict:
            account_move_dict.update(purchase_order_dict)
        account_move_dict.update(self.get_items(
            nfe, company_id, partner['partner_id'] or account_move_dict['partner_id'],
            account_move_dict, dfe,
            supplierinfo_automation, tax_automation, 
            fiscal_position_id=account_move_dict['fiscal_position_id'] \
                                    if 'fiscal_position_id' in account_move_dict \
                                            and account_move_dict['fiscal_position_id'] \
                                    else fiscal_position_id,
            purchase_order_id=purchase_order_dict and purchase_order_dict.get('purchase_id')
            or account_move_dict.get('purchase_id'),
            purchase_order_automation=purchase_order_automation
        ))
        # if not purchase_order_dict and purchase_order_automation:
        #     account_move_dict.update(self._l10n_br_allss_create_purchase_order_vals(
        #         account_move_dict, dfe))
        purchase_id = purchase_order_dict.get('purchase_id') or account_move_dict.get('purchase_id')
        if purchase_id:
            brw_purchase_order = self.env.get('purchase.order').sudo().browse(purchase_id)
            brw_purchase_order.state == 'draft' and brw_purchase_order.button_confirm()
        account_move_dict.update(self.get_infAdic(nfe))

        _logger.warning(f">>>>> ALLSS > import_nfe > move_type: {partner_vals['move_type']}")

        # invoice_default = self.env['account.move'].with_context(
        #     default_move_type=partner_vals['move_type'], default_company_id=company_id.id
        # ).default_get(['journal_id'])

        # journal_id = self.env['account.move'].with_context(
        #     force_company=company_id.id, 
        #     type=('sale' 
        #             if partner_vals['move_type']=='out_invoice' 
        #             else 'purchase')
        #     )._get_default_journal()

        tipo = 'sale' if partner_vals['move_type'] == 'out_invoice' else 'purchase'
        journal_id = self.l10n_br_allss_get_journal_id(company_id, tipo)

        _logger.warning(f">>>>> ALLSS > import_nfe > journal_id ({type(journal_id)}): {journal_id}")
        _logger.warning(f">>>>> ALLSS > import_nfe > journal_id.id ({type(journal_id.id)}): {journal_id.id}")
        _logger.warning(f">>>>> ALLSS > import_nfe > journal_id.name ({type(journal_id.name)}): {journal_id.name}")

        account_move_dict.update({'journal_id': journal_id.id})

        if 'l10n_br_allss_ms_code' not in account_move_dict and 'l10n_br_allss_ms_code' in journal_id._fields and journal_id.l10n_br_allss_ms_code:
            account_move_dict.update({'l10n_br_allss_ms_code': journal_id.l10n_br_allss_ms_code.sudo().id})

        transport_data = []
        transp_1 = self.get_transp(nfe)
        if transp_1:
            transport_data += transp_1
        mod_frete = '9'
        if hasattr(nfe.NFe.infNFe, 'transp'):
            mod_frete = get(nfe.NFe.infNFe.transp, 'modFrete', str)
        
        # ALLSS - Campo "l10n_br_allss_shipping_mode" substituido pelo "l10n_br_edi_freight_model" do módulo "l10n_br_edi"
        # account_move_dict.update({'l10n_br_allss_shipping_mode': mod_frete})
        # account_move_dict.update({'l10n_br_edi_freight_model': mod_frete})
        if mod_frete == "0":
            mod_frete = "CIF"
        elif mod_frete == "1":
            mod_frete = "FOB"
        elif mod_frete == "2":
            mod_frete = "Thirdparty"
        elif mod_frete == "3":
            mod_frete = "SenderVehicle"
        elif mod_frete == "4":
            mod_frete = "ReceiverVehicle"
        elif mod_frete == "9":
            mod_frete = "FreeShipping"
        else:
            mod_frete = ""
        account_move_dict.update({'l10n_br_edi_freight_model': mod_frete})

        transp_1 = self.get_reboque(nfe)
        if transp_1:
            transport_data += transp_1
        account_move_dict.update({'l10n_br_allss_trailer_ids': transport_data})
        account_move_dict.update({'l10n_br_allss_volume_ids': [(0, 0, self.get_vol(nfe))]})

        account_move_dict.update({'l10n_br_edi_payment_method': str(nfe.NFe.pag.detPag[0].tPag).zfill(2)
                            if hasattr(nfe.NFe, 'pag') and hasattr(nfe.NFe.pag, 'detPag') and len(nfe.NFe.pag.detPag) > 0
                            else '99'
                        })
        account_move_dict.update(self.get_cobr_dup(nfe))
        account_move_dict.update(self.get_det_pag(nfe))
        account_move_dict.pop('destinatary', False)
        if account_move_dict.get('fiscal_position_id') \
                and not isinstance(account_move_dict.get('fiscal_position_id'), int):
            account_move_dict['fiscal_position_id'] = account_move_dict.get('fiscal_position_id').id

        _logger.warning(f">>>>> ALLSS > import_nfe > account_move_dict para o create de account.move ({type(account_move_dict)}): {account_move_dict}")
        account_move = self.sudo().create(account_move_dict)
        _logger.warning(f">>>>> ALLSS > import_nfe > account_move ({type(account_move)}): {account_move}")
        return account_move

    def l10n_br_allss_get_journal_id(self, company_id, type):
        journal_id = False
        if type == 'purchase':
            journal_id = company_id.l10n_br_allss_vendor_journal_id
        if not journal_id:
            journal_id = self.env['account.journal'].sudo().search([
                ('company_id', '=', company_id.id), ('type', '=', type)], limit=1)
        return journal_id

    def existing_account_move(self, auto, nfe, partner_vals):
        if hasattr(nfe, 'protNFe'):
            protNFe = nfe.protNFe.infProt
        else:
            if auto:
                _logger.warning(f'>>>>> ALLSS > NF-e Import > XML invalido!')
                return False
            else:
                raise UserError('XML invalido!')

        chave_nfe = protNFe.chNFe

        account_move = self.env['account.move'].sudo().search([
                ('l10n_br_allss_nf_key', '=', chave_nfe),
                ('move_type', '=', partner_vals.get('move_type', 'in_invoice')),
                ('company_id', '=', partner_vals.get('company_id', self.env.company.id)),
                ('partner_id', '=', partner_vals.get('partner_id', False)),
                ('state', '!=', 'cancel'),
            ])

        return account_move

    def _create_partner(self, tag_nfe, destinatary):
        cnpj_cpf = None
        company_type = None
        is_company = None
        ender_tag = 'enderEmit' if destinatary else 'enderDest'

        if hasattr(tag_nfe, 'CNPJ'):
            cnpj_cpf = str(tag_nfe.CNPJ.text).zfill(14)
            company_type = 'company'
            is_company = True
        else:
            cnpj_cpf = str(tag_nfe.CPF.text).zfill(11)
            company_type = 'person'
            is_company = False

        cnpj_cpf = cnpj_cpf_format(cnpj_cpf)

        state_id = self.env['res.country.state'].sudo().search([
            ('code', '=', get(tag_nfe, ender_tag + '.UF')),
            ('country_id.code', '=', 'BR')])

        city_id = self.env['res.city'].sudo().search([
            ('l10n_br_allss_ibge_code', '=', get(tag_nfe, ender_tag + '.cMun', str)[2:]),
            ('state_id', '=', state_id.id)])

        partner = {
            'name': get(tag_nfe, 'xFant') or get(tag_nfe, 'xNome'),
            'street_name': get(tag_nfe, ender_tag + '.xLgr'),
            'street_number': get(tag_nfe, ender_tag + '.nro', str),
            'street2': get(tag_nfe, ender_tag + '.xBairro'),
            'city_id': city_id.id,
            'state_id': state_id.id,
            'zip': get(tag_nfe, ender_tag + '.CEP', str),
            'country_id': state_id.country_id.id,
            'phone': get(tag_nfe, ender_tag + '.fone'),
            'l10n_br_allss_state_registry_ids': [
                (0, 0, {'l10n_br_allss_code': tag_nfe.IE.text,
                        'l10n_br_allss_state_id': state_id.id,
                        'active_registry': True, }),
            ] if get(tag_nfe, 'IE', str) and len(tag_nfe.IE.text) > 1 else [],
            'l10n_br_allss_city_registry_ids': [
                (0, 0, {'l10n_br_allss_code': tag_nfe.IM.text,
                        'l10n_br_allss_state_id': state_id.id,
                        'l10n_br_allss_city_id': city_id.id,
                        'active_registry': True, }),
            ] if get(tag_nfe, 'IM', str) and len(tag_nfe.IM.text) > 1 else [],
            'vat': str(cnpj_cpf),
            'l10n_br_allss_corporate_name': get(tag_nfe, 'xNome'),
            'company_type': company_type,
            'is_company': is_company,
            'company_id': None,
        }

        if hasattr(tag_nfe, 'CNAE'):
            cnae = str(tag_nfe.CNAE.text)
            obj_res_cnae_registry = self.env.get('l10n.br.allss.res.cnae.registry')
            cnae_id = obj_res_cnae_registry.sudo().search([('l10n_br_allss_code', '=', cnae)], limit=1)
            if not cnae_id:
                cnae_id = obj_res_cnae_registry.sudo().create({'name': cnae, 'l10n_br_allss_code': cnae})
            partner.update({
                'l10n_br_allss_cnae_ids': [
                    (0, 0, {'l10n_br_allss_cnae_id': cnae_id.id})
                ]
            })

        partner_id = self.env['res.partner'].sudo().create(partner)
        partner_id.message_post(body="<ul><li>Parceiro criado através da importação\
                                de xml</li></ul>")

        return partner_id

    def _create_product(self, partner_id, nfe_item, uom_id=False):
        _logger.warning(f">>>>>>>>>> ALLSS > _create_product > nfe_item ({type(nfe_item)}): {nfe_item}")
        _logger.warning(f">>>>>>>>>> ALLSS > _create_product > self.env.ref('uom.product_uom_unit') ({type(self.env.ref('uom.product_uom_unit'))}): {self.env.ref('uom.product_uom_unit')}")
        _logger.warning(f">>>>>>>>>> ALLSS > _create_product > uom_id ({type(uom_id)}): {uom_id}")
        product_id = False
        params = self.env['ir.config_parameter'].sudo()
        seq_id = int(params.get_param(
            'l10n_br_allss_nfe_import_teste.l10n_br_allss_product_sequence_id', default=False))
        _logger.warning(f">>>>>>>>>> ALLSS > _create_product > seq_id ({type(seq_id)}): {seq_id}")
        if not seq_id:
            raise UserError(
                'A empresa não possui uma sequência de produto configurado!')
        ncm = get(nfe_item, 'NCM', str)
        
        ncm_id = self.env['l10n.br.allss.fiscal.ncm'].sudo().search([
            # ('l10n_br_allss_type', '=', 'product'),
            ('l10n_br_allss_type', '=', 'consu'),
            ('l10n_br_allss_code', '=', ncm[:4] + '.' + ncm[4:6] + '.' + ncm[6:])
        ], limit=1)
        if not ncm_id:
            ncm_id = self.env['l10n.br.allss.fiscal.ncm'].sudo().search([
                # ('l10n_br_allss_type', '=', 'product'),
                ('l10n_br_allss_type', '=', 'consu'),
                ('l10n_br_allss_code', '=', ncm)
            ], limit=1)
        if not ncm_id:
            ncm_id = self.env['l10n.br.allss.fiscal.ncm'].sudo().create({
                'name': 'NCM ' + ncm[:4] + '.' + ncm[4:6] + '.' + ncm[6:],
                'l10n_br_allss_level': 'subitem',
                'l10n_br_allss_type': 'consu',      # Antigo 'product'
                'l10n_br_allss_code': ncm[:4] + '.' + ncm[4:6] + '.' + ncm[6:],
            })

        sequence = self.env['ir.sequence'].sudo().browse(seq_id)
        code = sequence.next_by_id()
        product = {
            'default_code': code,
            'name': get(nfe_item, 'xProd') or 'Produto criado através da importação do arquivo XML da NF-e.',
            'purchase_ok': True,
            'sale_ok': False,
            'type': 'consu',
            'is_storable': True,
            'uom_id': uom_id or self.env.ref('uom.product_uom_unit').id or False,
            'uom_po_id': uom_id or self.env.ref('uom.product_uom_unit').id or False,
            'l10n_br_allss_fiscal_ncm_id': ncm_id.id,
            'standard_price': get(nfe_item, 'vUnCom'),
            'lst_price': 0.0,
            # todo ALLSS: está implementado o CEST?
            # 'l10n_br_allss_cest_id': get(nfe_item, 'CEST', str),
            'taxes_id': [],
            'supplier_taxes_id': [],
            'company_id': None,
        }
        if uom_id:
            product.update(dict(uom_id=uom_id))

        ean = get(nfe_item, 'cEAN', str)
        if ean != 'None' and ean != 'SEM GTIN':
            product['barcode'] = ean
        
        _logger.warning(f">>>>>>>>>> ALLSS > _create_product > product ({type(product)}): {product}")
        
        try:
            product_id = self.env['product.product'].sudo().create(product)
        
            _logger.warning(f">>>>>>>>>> ALLSS > _create_product > product_id ({type(product_id)}): {product_id}")

            self.env['product.supplierinfo'].sudo().create({
                'partner_id': partner_id,
                'product_id': product_id.id,
                'product_tmpl_id': product_id.product_tmpl_id.id,
                'product_code': get(nfe_item, 'cProd', str),
                'product_name': get(nfe_item, 'xProd') or 'Produto criado através da importação do arquivo XML da NF-e.',
                'product_uom': uom_id or self.env.ref('uom.product_uom_unit').id or False,
            })

            product_id.message_post(
                body="<ul><li>Produto criado através da importação \
                de xml</li></ul>")
        except Exception as e:
            _logger.error(f">>>>>>>>>> ALLSS > _create_product > Erro ao criar o produto: {e} ", exc_info=True)

        return product_id


    # def prepare_account_invoice_line_vals(self, item):
    #     if item.product_id:
    #         product = item.product_id.with_context(force_company=self.company_id.id)
    #         if product.property_account_expense_id:
    #             account_id = product.property_account_expense_id
    #         else:
    #             account_id = \
    #                 product.categ_id.property_account_expense_categ_id
    #     else:
    #         account_id = self.env['ir.property'].with_context(
    #             force_company=self.company_id.id).get(
    #             'property_account_expense_categ_id', 'product.category')

    #     vals = {
    #         'product_id': item.product_id.id,
    #         'product_uom_id': item.uom_id.id,
    #         'name': item.name if item.name else item.product_xprod,
    #         'quantity': item.quantidade,
    #         'price_unit': item.preco_unitario,
    #         'account_id': account_id.id,
    #     }
    #     return vals

    def _l10n_br_allss_get_purchase_order_vals(self, po_number=False):
        vals = {}
        if po_number:
            purchase_order_id = self.env.get('purchase.order').sudo().search(
                [('name', '=', po_number), ('state', '=', 'purchase')])
            if purchase_order_id.id:
                vals = {
                    'purchase_id': purchase_order_id.id,
                    'fiscal_position_id': purchase_order_id.fiscal_position_id.id,
                    # todo: payment_term_id não existe em account_move
                    # 'payment_term_id': purchase_order_id.payment_term_id.id,
                }
        return vals

    def _l10n_br_allss_create_purchase_order_vals(self, account_move_dict, dfe, dfe_item_xped):
        _logger.warning(f">>>>>>>>>>ALLSS > _l10n_br_allss_create_purchase_order_vals > self ({type(self)}): {self}")
        _logger.warning(f">>>>>>>>>>ALLSS > _l10n_br_allss_create_purchase_order_vals > account_move_dict ({type(account_move_dict)}): {account_move_dict}")
        _logger.warning(f">>>>>>>>>>ALLSS > _l10n_br_allss_create_purchase_order_vals > dfe ({type(dfe)}): {dfe}")
        purchase_order_vals = {
            'partner_id': (dfe and dfe.partner_id.id) or account_move_dict.get('partner_id', False),
            'fiscal_position_id': account_move_dict.get('fiscal_position_id').id,
            'payment_term_id': account_move_dict.get('invoice_payment_term_id'),
            'date_order': account_move_dict.get('invoice_date'),
            'date_planned': account_move_dict.get('invoice_date'),
        }
        po = dfe_item_xped or account_move_dict.get('l10n_br_allss_xpedcom')
        _logger.warning(f">>>>>>>>>>ALLSS > _l10n_br_allss_create_purchase_order_vals > po ({type(po)}): {po}")
        if po:
            purchase_order_vals.update({'name': po})
        _logger.warning(f">>>>>>>>>>ALLSS > _l10n_br_allss_create_purchase_order_vals > purchase_order_vals ({type(purchase_order_vals)}): {purchase_order_vals}")
        purchase_id = self.env.get('purchase.order').sudo().create(purchase_order_vals)
        _logger.warning(f">>>>>>>>>>ALLSS > _l10n_br_allss_create_purchase_order_vals > purchase_id ({type(purchase_id)}): {purchase_id}")
        return {'purchase_id': purchase_id.id}


    def dict_to_domain_tax(vals: dict, tol=1e-6) -> list:
        """
        Domain específico p/ localizar account.tax por atributos estáveis,
        usando tolerância em campos float.
        """
        stable_fields_eq = [
            'l10n_br_allss_account_tax_id',
            'amount_type',
            'type_tax_use',
            'l10n_br_allss_tax_rate_compute',
            'price_include_override',
            'tax_group_id',
        ]
        float_fields = [
            'amount',
            'amount_mva',
            'base_reduction',
        ]

        domain = []
        for f in stable_fields_eq:
            v = vals.get(f)
            if v not in (None, False, ''):
                domain.append((f, '=', v))

        for f in float_fields:
            v = vals.get(f)
            if v is None:
                continue
            # intervalo [v-tol, v+tol]
            domain += [(f, '>=', v - tol), (f, '<=', v + tol)]

        return domain


    def _get_tax(self, 
                 tax_name: str="", 
                 allss_account_tax_id: object=None, 
                 tax_dict: dict={}, 
                 tax_automation=False, 
                 **kwargs) -> object:
        """
        Busca ou cria um imposto (account.tax) com base em atributos estáveis.

        Args:
            tax_name (str): Nome do imposto a ser criado, se necessário.
            allss_account_tax_id (object): Especificidade Brasil do Imposto.
            tax_dict (dict): Dicionário com os atributos do imposto para fins de busca e criação.
            tax_automation (bool): Define se a criação automática de impostos está habilitada.
            kwargs: Argumentos adicionais, como 'icms_inter_tax_id'.

        Returns:
            
        """
        _logger.warning(f">>>>>>>>>> CHEGOU NO _get_tax >>>>>>>>>>>")

        message = ""
        _logger.warning(f">>>>>>>>>> CHEGOU pós message no _get_tax >>>>>>>>>>>")
        
        obj_account_tax = self.env.get('account.tax')
        _logger.warning(f">>>>>>>>>> CHEGOU NO obj_account_tax no _get_tax {obj_account_tax}>>>>>>>>>>>")

        obj_account_tax_group = self.env.get('account.tax.group')
        _logger.warning(f">>>>>>>>>> CHEGOU NO obj_account_tax_group no _get_tax {obj_account_tax_group}>>>>>>>>>>>")

        tax_ids = obj_account_tax.search(self.dict_to_domain_tax(tax_dict), limit=1)
        _logger.warning(f">>>>>>>>>> ALLSS > GET TAX > tax_ids ({type(tax_ids)}): {tax_ids}")
        if not tax_ids and tax_automation:
            tax_group_id = obj_account_tax_group.search([('name', '=', tax_name)], limit=1).id
            if not tax_group_id:
                tax_group_id = obj_account_tax_group.sudo().create({'name': tax_name}).id
            if obj_account_tax.search([('name', '=', tax_name)]):
                tax_name += '*'

            if 'name' not in tax_dict:
                tax_dict.update({'name': tax_name})
            if 'description' not in tax_dict:
                tax_dict.update({'description': tax_name})
            if 'tax_group_id' not in tax_dict:
                tax_dict.update({'tax_group_id': tax_group_id})

            tax_ids = obj_account_tax.sudo().create(tax_dict)

            tax_ids and tax_automation and allss_account_tax_id.ids \
                and kwargs.get('icms_inter_tax_id') \
                and allss_account_tax_id[0].write(
                    {'l10n_br_allss_tax_deduce_result': [(6, 0, [kwargs.get('icms_inter_tax_id')[1]])]}
                )

            message = f"<ul><li>Imposto criado através da importação do xml da NF-e<br/></li></ul>"

        return [tax_ids, message]



    def _create_supplierinfo(self, item, purchase_order_line,
                             automation=False):
        supplierinfo_id = self.env['product.supplierinfo'].sudo().search([
            ('partner_id', '=', purchase_order_line.order_id.partner_id.id),
            ('product_code', '=', item.product_cprod)])

        if not supplierinfo_id:
            vals = {
                'partner_id': purchase_order_line.order_id.partner_id.id,
                'product_name': item.product_xprod,
                'product_code': item.product_cprod,
                'product_tmpl_id': purchase_order_line.product_id.id,
            }

            self.env['product.supplierinfo'].sudo().create(vals)

            message = u"<ul><li>Produto do fornecedor criado através da\
                        importação do xml da NF-e %(nf)s. Produto\
                        do fornecedor %(codigo_produto_fornecedor)s\
                            - %(descricao_produto_fornecedor)s criado\
                        para o produto %(codigo_produto)s - \
                        %(descricao_produto)s<br/></li></ul>" % {
                'nf': self.numero,
                'codigo_produto_fornecedor':
                    item.product_cprod,
                'descricao_produto_fornecedor':
                    item.product_xprod,
                'codigo_produto':
                    purchase_order_line.product_id.default_code,
                'descricao_produto':
                    purchase_order_line.product_id.name,
            }

            return message

    # def _get_purchase_line_id(
    #         self, item, purchase_order_id, supplierinfo_automation=False):
    #     purchase_line_ids = self.env['purchase.order.line'].sudo().search([
    #         ('order_id', '=', purchase_order_id)], order='sequence')

    #     if not purchase_line_ids:
    #         return False, "Item de ordem de compra não localizado"

    #     purchase_line_id = purchase_line_ids[int(
    #         item.item_pedido_compra) - 1]

    #     if hasattr(purchase_line_id.product_id, 'seller_id'):
    #         seller_id = purchase_line_id.product_id.seller_id

    #         if seller_id and seller_id.product_code == item.product_cprod:
    #             return purchase_line_id
    #         else:
    #             return purchase_line_ids.filtered(
    #                 lambda x: x.product_id.seller_id.product_code ==
    #                           item.product_cprod)

    #     message = self._create_supplierinfo(
    #         item, purchase_line_id, supplierinfo_automation)
    #     return purchase_line_id, message

    def _get_company_account_move(self, auto, nfe, partner_automation):
        emit = nfe.NFe.infNFe.emit
        dest = nfe.NFe.infNFe.dest
        ###ALLSS - Anderson Coelho - 10/10/2023 - Inversão
        # nfe_type = 'in' if nfe.NFe.infNFe.ide.tpNF.text == '0' else 'out'
        nfe_type = 'in' if nfe.NFe.infNFe.ide.tpNF.text == '1' else 'out'
        tipo_operacao = ''

        _logger.warning(f">>>>> ALLSS > _get_company_account_move > nfe_type ({type(nfe_type)}): {nfe_type}")

        if hasattr(emit, 'CNPJ'):
            emit_cnpj_cpf = cnpj_cpf_format(str(emit.CNPJ.text).zfill(14))
        else:
            emit_cnpj_cpf = cnpj_cpf_format(str(emit.CPF.text).zfill(11))

        if hasattr(dest, 'CNPJ'):
            dest_cnpj_cpf = cnpj_cpf_format(str(dest.CNPJ.text).zfill(14))
        else:
            dest_cnpj_cpf = cnpj_cpf_format(str(dest.CPF.text).zfill(11))
        
        _logger.warning(f">>>>> ALLSS > _get_company_account_move > emit_cnpj_cpf ({type(emit_cnpj_cpf)}): {emit_cnpj_cpf}")
        _logger.warning(f">>>>> ALLSS > _get_company_account_move > dest_cnpj_cpf ({type(dest_cnpj_cpf)}): {dest_cnpj_cpf}")

        # !Importante
        # 1º pesquisa a empresa através do CNPJ, tanto emitente quanto dest.
        # 2º caso a empresa for destinatária usa o cnpj do emitente
        # para cadastrar parceiro senão usa o do destinatário
        # 3º o tipo de operação depende se a empresa emitiu ou não a nota
        # Se ela emitiu usa do xml o tipo, senão inverte o valor

        cnpj_cpf_partner = False
        destinatary = False
        company = self.env['res.company'].sudo().search(
            [('partner_id.vat', '=', dest_cnpj_cpf)])

        # company = self.env.company
        if not company:
            company = self.env['res.company'].sudo().search(
                [('partner_id.vat', '=', emit_cnpj_cpf)])
            if company:
                cnpj_cpf_partner = dest_cnpj_cpf
                ###ALLSS - Anderson Coelho - 10/10/2023 - Inversão
                # tipo_operacao = 'in_invoice' if nfe_type == 'in' else 'out_invoice'
                tipo_operacao = 'in_invoice' if nfe_type == 'out' else 'out_invoice'
                _logger.warning(f">>>>> ALLSS > _get_company_account_move > tipo_operacao 1 ({type(tipo_operacao)}): {tipo_operacao}")
            else:
                # self.sudo().message_post(body='XML não destinado nem emitido por esta empresa!')
                if auto:
                    _logger.warning(f'>>>>> ALLSS > NF-e Import > XML não destinado nem emitido por esta empresa!')
                    return False
                else:
                    raise UserError(
                        "XML não destinado nem emitido por esta empresa.")
        else:
            destinatary = True
            cnpj_cpf_partner = emit_cnpj_cpf
            ###ALLSS - Anderson Coelho - 10/10/2023 - Inversão
            # tipo_operacao = 'in_invoice' if nfe_type == 'out' else 'out_invoice'
            tipo_operacao = 'in_invoice' if nfe_type == 'in' else 'out_invoice'
            _logger.warning(f">>>>> ALLSS > _get_company_account_move > tipo_operacao 2 ({type(tipo_operacao)}): {tipo_operacao}")

        emit_id = self.env['res.partner'].sudo().search([
            ('vat', '=', cnpj_cpf_partner)], limit=1)

        if not partner_automation and not emit_id:
            # self.sudo().message_post(body='Parceiro não encontrado, caso deseje cadastrar um parceiro selecione a opção "Cadastrar Parceiro"!')
            if auto:
                _logger.warning(f'>>>>> ALLSS > NF-e Import > Parceiro não encontrado, caso deseje cadastrar um parceiro selecione a opção "Cadastrar Parceiro"!')
                return False
            else:
                raise UserError(
                    "Parceiro não encontrado, caso deseje cadastrar " +
                    "um parceiro selecione a opção 'Cadastrar Parceiro'!")

        return dict(
            company_id=company.id,
            move_type=tipo_operacao,
            partner_id=emit_id.id,
            destinatary=destinatary,
        )

    # ==================================================
    # Novos métodos para importação de XML
    # def get_basic_info(self, nfe):
    #     nfe_type = get(nfe.NFe.infNFe.ide, 'tpNF', str)
    #     total = nfe.NFe.infNFe.total.ICMSTot.vNF
    #     products = len(nfe.NFe.infNFe.det)
    #     vals = self.inspect_partner_from_nfe(nfe)
    #     already_imported = self.existing_account_move(nfe)
    #     return dict(
    #         already_imported=already_imported,
    #         nfe_type=nfe_type,
    #         amount_total=total,
    #         total_products=products,
    #         **vals
    #     )

    def inspect_partner_from_nfe(self, nfe):
        """
        Importação da sessão <emit> do xml
        """
        nfe_type = nfe.NFe.infNFe.ide.tpNF
        tag_nfe = None
        if nfe_type == 1:
            tag_nfe = nfe.NFe.infNFe.emit
        else:
            tag_nfe = nfe.NFe.infNFe.dest

        if hasattr(tag_nfe, 'CNPJ'):
            cnpj_cpf = cnpj_cpf_format(str(tag_nfe.CNPJ.text).zfill(14))
        else:
            cnpj_cpf = cnpj_cpf_format(str(tag_nfe.CPF.text).zfill(11))

        partner_id = self.env['res.partner'].sudo().search([
            ('vat', '=', cnpj_cpf)], limit=1)

        partner_data = "%s - %s" % (cnpj_cpf, tag_nfe.xNome)
        return dict(partner_id=partner_id.id, partner_data=partner_data)

    # def generate_account_move(self, auto, xml_nfe, create_partner):
    #     nfe = objectify.fromstring(xml_nfe)

    #     account_move_dict = {}
    #     if self.existing_account_move(nfe):
    #         raise UserError('Nota Fiscal já importada para o sistema!')

    #     partner_vals = self._get_company_account_move(auto, nfe, create_partner)
    #     company_id = self.env['res.company'].sudo().browse(partner_vals['company_id'])

    #     fiscal_position_id = company_id.l10n_br_allss_fiscal_position_id_automation or False

    #     account_move_dict.update(partner_vals)
    #     account_move_dict.update({
    #         'l10n_br_allss_nf_xml': base64.encodebytes(xml_nfe),
    #         'l10n_br_allss_nf_number': "NFe%08d.xml" % nfe.NFe.infNFe.ide.nNF
    #     })
    #     account_move_dict.update(self.get_protNFe(nfe, company_id))
    #     account_move_dict.update(self.get_main(nfe))
    #     partner = self.get_partner_nfe(
    #         nfe, partner_vals['destinatary'], create_partner)
    #     account_move_dict.update(
    #         self.get_ide(nfe, partner_vals['move_type'], fiscal_position_id))
    #     account_move_dict.update(partner)
    #     # ALLSS: Não usado
    #     # account_move_dict.sudo().update(self.get_ICMSTot(nfe))
    #     account_move_dict.update(self.get_items(
    #         nfe, company_id, partner['partner_id'],
    #         account_move_dict['partner_id'],
    #         False, False))
    #     account_move_dict.update(self.get_infAdic(nfe))
    #     # ALLSS: Não usado
    #     # account_move_dict.sudo().update(self.get_cobr_fat(nfe))
    #     transport_data = []
    #     transp_1 = self.get_transp(nfe)
    #     transp_1 and transport_data.append(transp_1)
    #     transp_1 = self.get_reboque(nfe)
    #     transp_1 and transport_data.append(transp_1)
    #     account_move_dict.update({'l10n_br_allss_trailer_ids': transport_data})
    #     account_move_dict.update({'l10n_br_allss_volume_ids': [(0, None, self.get_vol(nfe))]})
    #     account_move_dict.update(self.get_cobr_dup(nfe))
    #     account_move_dict.update(self.get_compra(nfe))
    #     account_move_dict.pop('destinatary', False)

    #     _logger(f">>>>> Import NF-e > generate_account_move > account_move_dict ({type(account_move_dict)}): {account_move_dict}")

    #     account_move = self.env['account.move'].sudo().create(account_move_dict)
    #     if account_move:
    #         account_move.sudo().write({
    #                         'l10n_br_allss_events_line_ids': [(0, 0, {
    #                                 'res_model_id': self.env['ir.model'].sudo().search([('model', '=', account_move._name)]).id,
    #                                 'res_id': account_move.id,
    #                                 'name': f"XML Importado com sucesso!",
    #                                 'l10n_br_allss_code': f'02.100',
    #                                 'l10n_br_allss_user_id': self.env.user.id,
    #                                 'l10n_br_allss_event_date': fields.datetime.now(),
    #                                 'l10n_br_allss_event_file': base64.encodebytes(xml_nfe),
    #                                 'l10n_br_allss_event_file_name': "NFe%08d.xml" % nfe.NFe.infNFe.ide.nNF,
    #                             })],
    #                     })

    #     return account_move

    def check_inconsistency_and_redirect(self):
        to_check = []
        for line in self.invoice_line_ids:
            if not line.product_id or not line.product_uom_id:
                to_check.append((0, 0, {
                    'eletronic_line_id': line.id,
                    'uom_id': line.product_uom_id.id,
                    'product_id': line.product_id.id,
                }))

        if to_check:
            wizard = self.env['wizard.nfe.configuration'].sudo().create({
                'eletronic_doc_id': self.id,
                'partner_id': self.partner_id.id,
                'nfe_item_ids': to_check
            })
            return {
                "type": "ir.actions.act_window",
                "res_model": "wizard.nfe.configuration",
                'view_type': 'form',
                'views': [[False, 'form']],
                "name": "Configuracao",
                "res_id": wizard.id,
                'flags': {'mode': 'edit'}
            }

    @contextmanager
    def _sync_dynamic_line(self, existing_key_fname, needed_vals_fname, needed_dirty_fname, line_type, container):
        def existing():
            return {
                line[existing_key_fname]: line
                for line in container['records'].line_ids
                if line[existing_key_fname]
            }

        def needed():
            res = {}
            for computed_needed in container['records'].mapped(needed_vals_fname):
                if computed_needed is False:
                    continue  # there was an invalidation, let's hope nothing needed to be changed...
                for key, values in computed_needed.items():
                    if key not in res:
                        res[key] = dict(values)
                    else:
                        ignore = True
                        for fname in res[key]:
                            if self.env['account.move.line']._fields[fname].type == 'monetary':
                                res[key][fname] += values[fname]
                                if res[key][fname]:
                                    ignore = False
                        if ignore:
                            del res[key]

            # Convert float values to their "ORM cache" one to prevent different rounding calculations
            for dict_key in res:
                move_id = dict_key.get('move_id')
                if not move_id:
                    continue
                record = self.env['account.move'].browse(move_id)
                for fname, current_value in res[dict_key].items():
                    field = self.env['account.move.line']._fields[fname]
                    if isinstance(current_value, float):
                        new_value = field.convert_to_cache(current_value, record)
                        res[dict_key][fname] = new_value

            return res

        def dirty():
            *path, dirty_fname = needed_dirty_fname.split('.')
            eligible_recs = container['records'].mapped('.'.join(path))
            if eligible_recs._name == 'account.move.line':
                eligible_recs = eligible_recs.filtered(lambda l: l.display_type != 'cogs')
            dirty_recs = eligible_recs.filtered(dirty_fname)
            return dirty_recs, dirty_fname

        existing_before = existing()
        needed_before = needed()
        dirty_recs_before, dirty_fname = dirty()
        dirty_recs_before[dirty_fname] = False
        yield
        dirty_recs_after, dirty_fname = dirty()
        if not dirty_recs_after:  # TODO improve filter
            return
        existing_after = existing()
        needed_after = needed()

        # Filter out deleted lines from `needed_before` to not recompute lines if not necessary or wanted
        line_ids = set(self.env['account.move.line'].browse(k['id'] for k in needed_before if 'id' in k).exists().ids)
        needed_before = {k: v for k, v in needed_before.items() if 'id' not in k or k['id'] in line_ids}

        # old key to new key for the same line
        inv_existing_before = {v: k for k, v in existing_before.items()}
        inv_existing_after = {v: k for k, v in existing_after.items()}
        before2after = {
            before: inv_existing_after[bline]
            for bline, before in inv_existing_before.items()
            if bline in inv_existing_after
        }

        if needed_after == needed_before:
            return

        to_delete = [
            line.id
            for key, line in existing_before.items()
            if key not in needed_after
               and key in existing_after
               and before2after[key] not in needed_after
        ]
        to_delete_set = set(to_delete)
        to_delete.extend(line.id
                         for key, line in existing_after.items()
                         if key not in needed_after and line.id not in to_delete_set
                         )
        to_create = {
            key: values
            for key, values in needed_after.items()
            if key not in existing_after
        }
        to_write = {
            existing_after[key]: values
            for key, values in needed_after.items()
            if key in existing_after
               and any(
                self.env['account.move.line']._fields[fname].convert_to_write(existing_after[key][fname], self)
                != values[fname]
                for fname in values
            )
        }

        while to_delete and to_create:
            key, values = to_create.popitem()
            line_id = to_delete.pop()
            self.env['account.move.line'].browse(line_id).write(
                {**key, **values, 'display_type': line_type}
            )
        if to_delete:
            self.env['account.move.line'].browse(to_delete).with_context(dynamic_unlink=True).unlink()
        if to_create:

            # ALLSS INICIO
            list_to_create = [
                {**key, **values, 'display_type': line_type}
                for key, values in to_create.items()
            ]
            list_to_create_portions = []
            if container.get('records').l10n_br_allss_nfe_xml_portions_data \
                    and list(filter(lambda p: not p.get('name'), list_to_create)):
                for val in list_to_create:
                    portions = eval(container.get('records').l10n_br_allss_nfe_xml_portions_data)
                    for portion in portions:
                        data = val.copy()
                        data.update({
                            'date_maturity': portion.get('date_maturity'),
                            'amount_currency': portion.get('amount_currency') * -1
                            if val.get('amount_currency') < 0 else portion.get('amount_currency'),
                            'l10n_br_allss_duplicate_number': portion.get('l10n_br_allss_duplicate_number'),
                            'name': 'Parcela %s' % portion.get('l10n_br_allss_duplicate_number'),
                        })

                        # ALLSS - Resolver arredondamento
                        if line_type == 'payment_term' and portions.__len__() == 1 \
                                and data.get('amount_currency') != val.get('amount_currency'):
                            data.update({'amount_currency': val.get('amount_currency')})

                        if data.get('balance'):
                            data.update({
                                'balance': portion.get('amount_currency') * -1
                                if data.get('balance') < 0 else portion.get('amount_currency'),
                            })
                        list_to_create_portions.append(data)
            if list_to_create_portions:
                list_to_create = list_to_create_portions
            self.env['account.move.line'].create(list_to_create)
            # ALLSS FIM

        if to_write:
            for line, values in to_write.items():
                line.write(values)

    # def _prepare_account_move_vals(self):

    #     ###ALLSS - Anderson Coelho - 10/10/2023 - Correção do conteúdo da variável tipo_operacao
    #     _logger.warning(f'>>>>> ALLSS > _prepare_account_move_vals > self.tipo_operacao ({type(self.tipo_operacao)}): {self.tipo_operacao}')
    #     # operation = 'in_invoice' \
    #     #     if self.tipo_operacao == 'entrada' else 'out_invoice'
    #     operation = 'in_invoice' \
    #         if self.tipo_operacao == 'entrada' else 'out_invoice'


    #     journal_id = self.env['account.move'].with_context(
    #         default_move_type=operation, default_company_id=self.company_id.id
    #     ).default_get(['journal_id'])['journal_id']
    #     partner = self.partner_id.with_context(force_company=self.company_id.id)
    #     account_id = partner.property_account_payable_id.id \
    #         if operation == 'in_invoice' else \
    #         partner.property_account_receivable_id.id

    #     vals = {
    #         'company_id': self.company_id.id,
    #         'move_type': operation,
    #         'state': 'draft',
    #         'invoice_origin': self.pedido_compra,
    #         'ref': "%s/%s" % (self.numero, self.serie_documento),
    #         'invoice_date': self.data_emissao.date(),
    #         'date': self.data_emissao.date(),
    #         'partner_id': self.partner_id.id,
    #         'journal_id': journal_id,
    #         'amount_total': self.valor_final,
    #         'invoice_payment_term_id': self.env.ref('l10n_br_nfe_import.payment_term_for_import').id,
    #     }
    #     return vals

    # def prepare_extra_line_items(self, product, price):
    #     product = product.with_context(force_company=self.company_id.id)
    #     if product.property_account_expense_id:
    #         account_id = product.property_account_expense_id
    #     else:
    #         account_id = \
    #             product.categ_id.property_account_expense_categ_id
    #     return {
    #         'product_id': product.id,
    #         'product_uom_id': product.uom_id.id,
    #         'name': product.name if product.name else product.product_xprod,
    #         'quantity': 1.0,
    #         'price_unit': price,
    #         'account_id': account_id.id,
    #     }

    # def generate_account_move(self):
    #     next_action = self.check_inconsistency_and_redirect()
    #     if next_action:
    #         return next_action
    #
    #     vals = self._prepare_account_invoice_vals()
    #
    #     # purchase_order_vals = self._l10n_br_allss_get_purchase_order_vals(self.pedido_compra)
    #     # purchase_order_id = None
    #     # if purchase_order_vals:
    #     #     vals.sudo().update(purchase_order_vals)
    #     #     purchase_order_id = vals['purchase_id']
    #
    #     items = []
    #     for item in self.document_line_ids:
    #         invoice_item = self.prepare_account_invoice_line_vals(item)
    #         items.append((0, 0, invoice_item))
    #
    #     if self.valor_ipi:
    #         product = self.env.ref("l10n_br_nfe_import.product_product_tax_ipi")
    #         items.append((0, 0, self.prepare_extra_line_items(product, self.valor_ipi)))
    #
    #     if self.valor_icmsst:
    #         product = self.env.ref("l10n_br_nfe_import.product_product_tax_icmsst")
    #         items.append((0, 0, self.prepare_extra_line_items(product, self.valor_icmsst)))
    #
    #     if self.valor_frete:
    #         product = self.env.ref("l10n_br_account.product_product_delivery")
    #         items.append((0, 0, self.prepare_extra_line_items(product, self.valor_frete)))
    #
    #     if self.valor_despesas:
    #         product = self.env.ref("l10n_br_account.product_product_expense")
    #         items.append((0, 0, self.prepare_extra_line_items(product, self.valor_despesas)))
    #
    #     if self.valor_seguro:
    #         product = self.env.ref("l10n_br_account.product_product_insurance")
    #         items.append((0, 0, self.prepare_extra_line_items(product, self.valor_seguro)))
    #
    #     vals['invoice_line_ids'] = items
    #     account_invoice = self.env['account.move'].sudo().create(vals)
    #     account_invoice.message_post(
    #         body="<ul><li>Fatura criada através da do xml da NF-e %s</li></ul>" % self.numero)
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Fatura',
    #         'res_model': 'account.move',
    #         'res_id': account_invoice.id,
    #         'view_type': 'form',
    #         'views': [[False, 'form']],
    #         'flags': {'mode': 'readonly'}
    #     }


class AllssAccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_br_allss_product_ean = fields.Char('EAN do Produto (XML)')
    l10n_br_allss_product_cprod = fields.Char('Cód .Fornecedor (XML)')
    l10n_br_allss_product_xprod = fields.Char('Nome do produto (XML)')
