<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE eagle SYSTEM "eagle.dtd">
<eagle version="9.6.2">
<drawing>
<settings>
<setting alwaysvectorfont="no"/>
<setting verticaltext="up"/>
</settings>
<grid distance="0.1" unitdist="inch" unit="inch" style="lines" multiple="1" display="no" altdistance="0.01" altunitdist="inch" altunit="inch"/>
<layers>
<layer number="1" name="Top" color="4" fill="1" visible="no" active="no"/>
<layer number="16" name="Bottom" color="1" fill="1" visible="no" active="no"/>
<layer number="17" name="Pads" color="2" fill="1" visible="no" active="no"/>
<layer number="18" name="Vias" color="2" fill="1" visible="no" active="no"/>
<layer number="19" name="Unrouted" color="6" fill="1" visible="no" active="no"/>
<layer number="20" name="Dimension" color="15" fill="1" visible="no" active="no"/>
<layer number="21" name="tPlace" color="7" fill="1" visible="no" active="no"/>
<layer number="22" name="bPlace" color="7" fill="1" visible="no" active="no"/>
<layer number="23" name="tOrigins" color="15" fill="1" visible="no" active="no"/>
<layer number="24" name="bOrigins" color="15" fill="1" visible="no" active="no"/>
<layer number="25" name="tNames" color="7" fill="1" visible="no" active="no"/>
<layer number="26" name="bNames" color="7" fill="1" visible="no" active="no"/>
<layer number="27" name="tValues" color="7" fill="1" visible="no" active="no"/>
<layer number="28" name="bValues" color="7" fill="1" visible="no" active="no"/>
<layer number="29" name="tStop" color="7" fill="3" visible="no" active="no"/>
<layer number="30" name="bStop" color="7" fill="6" visible="no" active="no"/>
<layer number="51" name="tDocu" color="7" fill="1" visible="no" active="no"/>
<layer number="52" name="bDocu" color="7" fill="1" visible="no" active="no"/>
<layer number="91" name="Nets" color="2" fill="1" visible="yes" active="yes"/>
<layer number="92" name="Busses" color="1" fill="1" visible="yes" active="yes"/>
<layer number="93" name="Pins" color="2" fill="1" visible="no" active="yes"/>
<layer number="94" name="Symbols" color="4" fill="1" visible="yes" active="yes"/>
<layer number="95" name="Names" color="7" fill="1" visible="yes" active="yes"/>
<layer number="96" name="Values" color="7" fill="1" visible="yes" active="yes"/>
<layer number="97" name="Info" color="7" fill="1" visible="yes" active="yes"/>
<layer number="98" name="Guide" color="6" fill="1" visible="yes" active="yes"/>
</layers>
<schematic xreflabel="%F%N/%S.%C%R" xrefpart="/%S.%C%R">
<description>Turbidity probe v3.1 - ESP32 direct solder wiring</description>
<libraries>
<library name="FISHDO">
<description>Turbidity probe v3.1 schematic-only symbols</description>
<packages>
</packages>
<symbols>
<symbol name="R">
<wire x1="-2.54" y1="0.889" x2="2.54" y2="0.889" width="0.2032" layer="94"/>
<wire x1="2.54" y1="0.889" x2="2.54" y2="-0.889" width="0.2032" layer="94"/>
<wire x1="2.54" y1="-0.889" x2="-2.54" y2="-0.889" width="0.2032" layer="94"/>
<wire x1="-2.54" y1="-0.889" x2="-2.54" y2="0.889" width="0.2032" layer="94"/>
<text x="-3.81" y="1.524" size="1.778" layer="95">&gt;NAME</text>
<text x="-3.81" y="-3.302" size="1.778" layer="96">&gt;VALUE</text>
<pin name="1" x="-5.08" y="0" visible="off" length="short" direction="pas" swaplevel="1"/>
<pin name="2" x="5.08" y="0" visible="off" length="short" direction="pas" swaplevel="1" rot="R180"/>
</symbol>
<symbol name="LED">
<wire x1="-2.032" y1="2.54" x2="2.032" y2="2.54" width="0.2032" layer="94"/>
<wire x1="2.032" y1="2.54" x2="0" y2="-1.27" width="0.2032" layer="94"/>
<wire x1="0" y1="-1.27" x2="-2.032" y2="2.54" width="0.2032" layer="94"/>
<wire x1="-2.032" y1="-1.27" x2="2.032" y2="-1.27" width="0.2032" layer="94"/>
<wire x1="0" y1="-1.27" x2="0" y2="-2.54" width="0.2032" layer="94"/>
<wire x1="-2.794" y1="1.524" x2="-4.318" y2="3.048" width="0.1524" layer="94"/>
<wire x1="-4.318" y1="3.048" x2="-3.556" y2="3.048" width="0.1524" layer="94"/>
<wire x1="-4.318" y1="3.048" x2="-4.318" y2="2.286" width="0.1524" layer="94"/>
<wire x1="-2.794" y1="-0.254" x2="-4.318" y2="1.27" width="0.1524" layer="94"/>
<wire x1="-4.318" y1="1.27" x2="-3.556" y2="1.27" width="0.1524" layer="94"/>
<wire x1="-4.318" y1="1.27" x2="-4.318" y2="0.508" width="0.1524" layer="94"/>
<text x="3.302" y="1.524" size="1.778" layer="95">&gt;NAME</text>
<text x="3.302" y="-1.27" size="1.778" layer="96">&gt;VALUE</text>
<pin name="A" x="0" y="5.08" visible="off" length="short" direction="pas" rot="R270"/>
<pin name="C" x="0" y="-5.08" visible="off" length="short" direction="pas" rot="R90"/>
</symbol>
<symbol name="PHOTOTRANS">
<circle x="0" y="0" radius="2.8194" width="0.1524" layer="94"/>
<wire x1="-1.27" y1="1.397" x2="-1.27" y2="-1.397" width="0.4064" layer="94"/>
<wire x1="-1.27" y1="0.635" x2="1.27" y2="1.905" width="0.2032" layer="94"/>
<wire x1="1.27" y1="1.905" x2="1.27" y2="2.54" width="0.2032" layer="94"/>
<wire x1="1.27" y1="2.54" x2="0" y2="2.54" width="0.2032" layer="94"/>
<wire x1="-1.27" y1="-0.635" x2="1.27" y2="-1.905" width="0.2032" layer="94"/>
<wire x1="1.27" y1="-1.905" x2="1.27" y2="-2.54" width="0.2032" layer="94"/>
<wire x1="1.27" y1="-2.54" x2="0" y2="-2.54" width="0.2032" layer="94"/>
<wire x1="6.35" y1="2.54" x2="3.81" y2="1.27" width="0.1524" layer="94"/>
<wire x1="3.81" y1="1.27" x2="4.572" y2="1.27" width="0.1524" layer="94"/>
<wire x1="3.81" y1="1.27" x2="4.064" y2="2.032" width="0.1524" layer="94"/>
<wire x1="6.35" y1="0.508" x2="3.81" y2="-0.762" width="0.1524" layer="94"/>
<wire x1="3.81" y1="-0.762" x2="4.572" y2="-0.762" width="0.1524" layer="94"/>
<wire x1="3.81" y1="-0.762" x2="4.064" y2="0" width="0.1524" layer="94"/>
<text x="-11.43" y="1.27" size="1.778" layer="95">&gt;NAME</text>
<text x="-11.43" y="-2.54" size="1.778" layer="96">&gt;VALUE</text>
<pin name="C" x="0" y="5.08" visible="off" length="short" direction="pas" rot="R270"/>
<pin name="E" x="0" y="-5.08" visible="off" length="short" direction="pas" rot="R90"/>
</symbol>
<symbol name="DS18B20">
<wire x1="-2.54" y1="5.08" x2="12.7" y2="5.08" width="0.2032" layer="94"/>
<wire x1="12.7" y1="5.08" x2="12.7" y2="-5.08" width="0.2032" layer="94"/>
<wire x1="12.7" y1="-5.08" x2="-2.54" y2="-5.08" width="0.2032" layer="94"/>
<wire x1="-2.54" y1="-5.08" x2="-2.54" y2="5.08" width="0.2032" layer="94"/>
<text x="-2.54" y="5.842" size="1.778" layer="95">&gt;NAME</text>
<text x="-2.54" y="-7.62" size="1.778" layer="96">&gt;VALUE</text>
<pin name="VDD" x="-7.62" y="2.54" visible="pin" length="middle" direction="pwr"/>
<pin name="DQ" x="-7.62" y="0" visible="pin" length="middle" direction="out"/>
<pin name="GND" x="-7.62" y="-2.54" visible="pin" length="middle" direction="pwr"/>
</symbol>
<symbol name="GND">
<wire x1="-1.905" y1="0" x2="1.905" y2="0" width="0.3048" layer="94"/>
<wire x1="-1.27" y1="-0.635" x2="1.27" y2="-0.635" width="0.3048" layer="94"/>
<wire x1="-0.635" y1="-1.27" x2="0.635" y2="-1.27" width="0.3048" layer="94"/>
<text x="-2.54" y="-3.81" size="1.778" layer="96">&gt;VALUE</text>
<pin name="GND" x="0" y="2.54" visible="off" length="short" direction="sup" rot="R270"/>
</symbol>
<symbol name="P3V3">
<wire x1="-1.905" y1="0" x2="1.905" y2="0" width="0.3048" layer="94"/>
<text x="-2.54" y="1.016" size="1.778" layer="96">&gt;VALUE</text>
<pin name="+3V3" x="0" y="-2.54" visible="off" length="short" direction="sup" rot="R90"/>
</symbol>
<symbol name="ESP32DEVKIT">
<wire x1="-15.24" y1="27.94" x2="15.24" y2="27.94" width="0.4064" layer="94"/>
<wire x1="15.24" y1="27.94" x2="15.24" y2="-27.94" width="0.4064" layer="94"/>
<wire x1="15.24" y1="-27.94" x2="-15.24" y2="-27.94" width="0.4064" layer="94"/>
<wire x1="-15.24" y1="-27.94" x2="-15.24" y2="27.94" width="0.4064" layer="94"/>
<text x="-15.24" y="28.702" size="1.778" layer="95">&gt;NAME</text>
<text x="-15.24" y="-31.242" size="1.778" layer="96">&gt;VALUE</text>
<text x="-4.445" y="23.876" size="1.778" layer="97">USB</text>
<pin name="3V3" x="-20.32" y="22.86" visible="pin" length="middle" direction="pwr"/>
<pin name="EN" x="-20.32" y="20.32" visible="pin" length="middle" direction="in"/>
<pin name="SVP" x="-20.32" y="17.78" visible="pin" length="middle" direction="in"/>
<pin name="SVN" x="-20.32" y="15.24" visible="pin" length="middle" direction="in"/>
<pin name="P34" x="-20.32" y="12.7" visible="pin" length="middle" direction="in"/>
<pin name="P35" x="-20.32" y="10.16" visible="pin" length="middle" direction="in"/>
<pin name="P32" x="-20.32" y="7.62" visible="pin" length="middle" direction="io"/>
<pin name="P33" x="-20.32" y="5.08" visible="pin" length="middle" direction="io"/>
<pin name="P25" x="-20.32" y="2.54" visible="pin" length="middle" direction="io"/>
<pin name="P26" x="-20.32" y="0" visible="pin" length="middle" direction="io"/>
<pin name="P27" x="-20.32" y="-2.54" visible="pin" length="middle" direction="io"/>
<pin name="P14" x="-20.32" y="-5.08" visible="pin" length="middle" direction="io"/>
<pin name="P12" x="-20.32" y="-7.62" visible="pin" length="middle" direction="io"/>
<pin name="GND1" x="-20.32" y="-10.16" visible="pin" length="middle" direction="pwr"/>
<pin name="P13" x="-20.32" y="-12.7" visible="pin" length="middle" direction="io"/>
<pin name="SD2" x="-20.32" y="-15.24" visible="pin" length="middle" direction="nc"/>
<pin name="SD3" x="-20.32" y="-17.78" visible="pin" length="middle" direction="nc"/>
<pin name="CMD" x="-20.32" y="-20.32" visible="pin" length="middle" direction="nc"/>
<pin name="5V" x="-20.32" y="-22.86" visible="pin" length="middle" direction="pwr"/>
<pin name="GND2" x="20.32" y="22.86" visible="pin" length="middle" direction="pwr" rot="R180"/>
<pin name="P23" x="20.32" y="20.32" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="P22" x="20.32" y="17.78" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="TX" x="20.32" y="15.24" visible="pin" length="middle" direction="out" rot="R180"/>
<pin name="RX" x="20.32" y="12.7" visible="pin" length="middle" direction="in" rot="R180"/>
<pin name="P21" x="20.32" y="10.16" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="GND3" x="20.32" y="7.62" visible="pin" length="middle" direction="pwr" rot="R180"/>
<pin name="P19" x="20.32" y="5.08" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="P18" x="20.32" y="2.54" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="P5" x="20.32" y="0" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="P10" x="20.32" y="-2.54" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="P16" x="20.32" y="-5.08" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="P4" x="20.32" y="-7.62" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="P0" x="20.32" y="-10.16" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="P2" x="20.32" y="-12.7" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="P15" x="20.32" y="-15.24" visible="pin" length="middle" direction="io" rot="R180"/>
<pin name="SD1" x="20.32" y="-17.78" visible="pin" length="middle" direction="nc" rot="R180"/>
<pin name="SD0" x="20.32" y="-20.32" visible="pin" length="middle" direction="nc" rot="R180"/>
<pin name="CLK" x="20.32" y="-22.86" visible="pin" length="middle" direction="nc" rot="R180"/>
</symbol>
</symbols>
<devicesets>
<deviceset name="R" prefix="R" uservalue="yes">
<gates>
<gate name="G$1" symbol="R" x="0" y="0"/>
</gates>
<devices>
<device name="">
<technologies>
<technology name=""/>
</technologies>
</device>
</devices>
</deviceset>
<deviceset name="LED" prefix="D" uservalue="yes">
<gates>
<gate name="G$1" symbol="LED" x="0" y="0"/>
</gates>
<devices>
<device name="">
<technologies>
<technology name=""/>
</technologies>
</device>
</devices>
</deviceset>
<deviceset name="PHOTOTRANS" prefix="Q" uservalue="yes">
<gates>
<gate name="G$1" symbol="PHOTOTRANS" x="0" y="0"/>
</gates>
<devices>
<device name="">
<technologies>
<technology name=""/>
</technologies>
</device>
</devices>
</deviceset>
<deviceset name="DS18B20" prefix="U" uservalue="yes">
<gates>
<gate name="G$1" symbol="DS18B20" x="0" y="0"/>
</gates>
<devices>
<device name="">
<technologies>
<technology name=""/>
</technologies>
</device>
</devices>
</deviceset>
<deviceset name="ESP32DEVKIT" prefix="U" uservalue="yes">
<gates>
<gate name="G$1" symbol="ESP32DEVKIT" x="0" y="0"/>
</gates>
<devices>
<device name="">
<technologies>
<technology name=""/>
</technologies>
</device>
</devices>
</deviceset>
<deviceset name="GND" prefix="SUPPLY">
<gates>
<gate name="G$1" symbol="GND" x="0" y="0" addlevel="request"/>
</gates>
<devices>
<device name="">
<technologies>
<technology name=""/>
</technologies>
</device>
</devices>
</deviceset>
<deviceset name="+3V3" prefix="SUPPLY">
<gates>
<gate name="G$1" symbol="P3V3" x="0" y="0" addlevel="request"/>
</gates>
<devices>
<device name="">
<technologies>
<technology name=""/>
</technologies>
</device>
</devices>
</deviceset>
</devicesets>
</library>
</libraries>
<attributes>
</attributes>
<variantdefs>
</variantdefs>
<classes>
<class number="0" name="default" width="0" drill="0">
</class>
</classes>
<parts>
<part name="U1" library="FISHDO" deviceset="ESP32DEVKIT" device="" value="ESP32 DevKit (WROOM-32)"/>
<part name="R1" library="FISHDO" deviceset="R" device="" value="150R"/>
<part name="R2" library="FISHDO" deviceset="R" device="" value="330R"/>
<part name="R3" library="FISHDO" deviceset="R" device="" value="680R"/>
<part name="R4" library="FISHDO" deviceset="R" device="" value="22R"/>
<part name="R5" library="FISHDO" deviceset="R" device="" value="15k"/>
<part name="R6" library="FISHDO" deviceset="R" device="" value="4k7"/>
<part name="D1" library="FISHDO" deviceset="LED" device="" value="IR LED 850nm"/>
<part name="Q1" library="FISHDO" deviceset="PHOTOTRANS" device="" value="D4184-2"/>
<part name="U2" library="FISHDO" deviceset="DS18B20" device="" value="DS18B20"/>
<part name="SUPV1" library="FISHDO" deviceset="+3V3" device=""/>
<part name="SUPV2" library="FISHDO" deviceset="+3V3" device=""/>
<part name="SUPV3" library="FISHDO" deviceset="+3V3" device=""/>
<part name="SUPV4" library="FISHDO" deviceset="+3V3" device=""/>
<part name="SUPG1" library="FISHDO" deviceset="GND" device=""/>
<part name="SUPG2" library="FISHDO" deviceset="GND" device=""/>
<part name="SUPG3" library="FISHDO" deviceset="GND" device=""/>
<part name="SUPG4" library="FISHDO" deviceset="GND" device=""/>
</parts>
<sheets>
<sheet>
<plain>
<text x="-88.9" y="48.26" size="3.048" layer="97">TURBIDITY PROBE v3.1  -  ESP32 DIRECT-SOLDER WIRING</text>
<text x="-88.9" y="43.18" size="1.778" layer="97">Source of truth: 05_JEPUM / TAKDO-PROBE / 04_HWAKJEONG-SAYANG.md   (v3.1 freeze, 2026-07-27)</text>
<text x="-88.9" y="38.1" size="1.778" layer="97">ACTIVE PART = ESP32 ONLY.    NO OP-AMP.    NO CAPACITOR.</text>
<wire x1="-55.88" y1="-20.32" x2="-71.12" y2="-20.32" width="0.1524" layer="97"/>
<wire x1="-71.12" y1="-20.32" x2="-69.088" y2="-19.304" width="0.1524" layer="97"/>
<wire x1="-71.12" y1="-20.32" x2="-69.088" y2="-21.336" width="0.1524" layer="97"/>
<text x="-69.85" y="-15.24" size="1.778" layer="97">L=50mm 850nm</text>
<text x="24.13" y="14.224" size="1.778" layer="97">1-Wire pull-up</text>
<text x="-88.9" y="-50.8" size="1.778" layer="97">NET SENSE = GPIO36 (silk SVP)      NET SIG = GPIO34 (silk P34)      NET DQ = GPIO4 (silk P4)</text>
<text x="-88.9" y="-55.88" size="1.778" layer="97">R-DAC 8-step drive: P27-150R (b2), P26-330R (b1), P25-680R (b0).  OFF state = pinMode INPUT (hi-Z), never LOW.</text>
<text x="-88.9" y="-60.96" size="1.778" layer="97">CAUTION: Q1 collector to 3V3 ONLY. 5V pushes node N above 3.3 V and destroys the ADC pin.</text>
<text x="-88.9" y="-66.04" size="1.778" layer="97">R5 = 15k is provisional (04_HWAKJEONG-SAYANG 5-1). Fallback 6k8 if repeat scatter &gt; 0.1 %.</text>
<text x="-88.9" y="-71.12" size="1.778" layer="97">Optical path is open water. No transparent tube (it would act as a light guide). Spine = M3 stainless.</text>
</plain>
<instances>
<instance part="U1" gate="G$1" x="0" y="0" smashed="yes">
<attribute name="NAME" x="-15.24" y="28.702" size="1.778" layer="95"/>
<attribute name="VALUE" x="-15.24" y="-31.242" size="1.778" layer="96"/>
</instance>
<instance part="R3" gate="G$1" x="-45.72" y="2.54" smashed="yes">
<attribute name="NAME" x="-49.53" y="4.064" size="1.778" layer="95"/>
<attribute name="VALUE" x="-44.45" y="4.064" size="1.778" layer="96"/>
</instance>
<instance part="R2" gate="G$1" x="-45.72" y="-5.08" smashed="yes">
<attribute name="NAME" x="-49.53" y="-3.556" size="1.778" layer="95"/>
<attribute name="VALUE" x="-44.45" y="-3.556" size="1.778" layer="96"/>
</instance>
<instance part="R1" gate="G$1" x="-45.72" y="-12.7" smashed="yes">
<attribute name="NAME" x="-49.53" y="-11.176" size="1.778" layer="95"/>
<attribute name="VALUE" x="-44.45" y="-11.176" size="1.778" layer="96"/>
</instance>
<instance part="D1" gate="G$1" x="-50.8" y="-20.32" smashed="yes">
<attribute name="NAME" x="-47.498" y="-18.796" size="1.778" layer="95"/>
<attribute name="VALUE" x="-47.498" y="-21.59" size="1.778" layer="96"/>
</instance>
<instance part="R4" gate="G$1" x="-50.8" y="-33.02" rot="R90" smashed="yes">
<attribute name="NAME" x="-53.594" y="-36.83" size="1.778" layer="95" rot="R90"/>
<attribute name="VALUE" x="-46.228" y="-36.83" size="1.778" layer="96" rot="R90"/>
</instance>
<instance part="Q1" gate="G$1" x="-76.2" y="-20.32" smashed="yes">
<attribute name="NAME" x="-88.9" y="-17.78" size="1.778" layer="95"/>
<attribute name="VALUE" x="-88.9" y="-21.336" size="1.778" layer="96"/>
</instance>
<instance part="R5" gate="G$1" x="-76.2" y="-33.02" rot="R90" smashed="yes">
<attribute name="NAME" x="-78.994" y="-36.83" size="1.778" layer="95" rot="R90"/>
<attribute name="VALUE" x="-71.628" y="-36.83" size="1.778" layer="96" rot="R90"/>
</instance>
<instance part="U2" gate="G$1" x="53.34" y="-7.62" smashed="yes">
<attribute name="NAME" x="50.8" y="-1.778" size="1.778" layer="95"/>
<attribute name="VALUE" x="50.8" y="-15.24" size="1.778" layer="96"/>
</instance>
<instance part="R6" gate="G$1" x="33.02" y="0" rot="R90" smashed="yes">
<attribute name="NAME" x="30.226" y="-3.81" size="1.778" layer="95" rot="R90"/>
<attribute name="VALUE" x="37.592" y="-3.81" size="1.778" layer="96" rot="R90"/>
</instance>
<instance part="SUPV1" gate="G$1" x="-27.94" y="25.4" smashed="yes">
<attribute name="VALUE" x="-30.48" y="26.416" size="1.778" layer="96"/>
</instance>
<instance part="SUPV2" gate="G$1" x="-76.2" y="-10.16" smashed="yes">
<attribute name="VALUE" x="-78.74" y="-9.144" size="1.778" layer="96"/>
</instance>
<instance part="SUPV3" gate="G$1" x="40.64" y="5.08" smashed="yes">
<attribute name="VALUE" x="38.1" y="6.096" size="1.778" layer="96"/>
</instance>
<instance part="SUPV4" gate="G$1" x="33.02" y="10.16" smashed="yes">
<attribute name="VALUE" x="30.48" y="11.176" size="1.778" layer="96"/>
</instance>
<instance part="SUPG1" gate="G$1" x="-25.4" y="-12.7" smashed="yes">
<attribute name="VALUE" x="-27.94" y="-16.51" size="1.778" layer="96"/>
</instance>
<instance part="SUPG2" gate="G$1" x="-50.8" y="-43.18" smashed="yes">
<attribute name="VALUE" x="-53.34" y="-46.99" size="1.778" layer="96"/>
</instance>
<instance part="SUPG3" gate="G$1" x="-76.2" y="-43.18" smashed="yes">
<attribute name="VALUE" x="-78.74" y="-46.99" size="1.778" layer="96"/>
</instance>
<instance part="SUPG4" gate="G$1" x="40.64" y="-17.78" smashed="yes">
<attribute name="VALUE" x="38.1" y="-21.59" size="1.778" layer="96"/>
</instance>
</instances>
<busses>
</busses>
<nets>
<net name="NODE_A" class="0">
<segment>
<wire x1="-50.8" y1="2.54" x2="-50.8" y2="-5.08" width="0.1524" layer="91"/>
<wire x1="-50.8" y1="-5.08" x2="-50.8" y2="-12.7" width="0.1524" layer="91"/>
<wire x1="-50.8" y1="-12.7" x2="-50.8" y2="-15.24" width="0.1524" layer="91"/>
<junction x="-50.8" y="-5.08"/>
<junction x="-50.8" y="-12.7"/>
<pinref part="R3" gate="G$1" pin="1"/>
<pinref part="R2" gate="G$1" pin="1"/>
<pinref part="R1" gate="G$1" pin="1"/>
<pinref part="D1" gate="G$1" pin="A"/>
<label x="-59.69" y="-1.27" size="1.778" layer="95"/>
</segment>
</net>
<net name="GPIO25" class="0">
<segment>
<wire x1="-40.64" y1="2.54" x2="-20.32" y2="2.54" width="0.1524" layer="91"/>
<pinref part="R3" gate="G$1" pin="2"/>
<pinref part="U1" gate="G$1" pin="P25"/>
</segment>
</net>
<net name="GPIO26" class="0">
<segment>
<wire x1="-40.64" y1="-5.08" x2="-30.48" y2="-5.08" width="0.1524" layer="91"/>
<wire x1="-30.48" y1="-5.08" x2="-30.48" y2="0" width="0.1524" layer="91"/>
<wire x1="-30.48" y1="0" x2="-20.32" y2="0" width="0.1524" layer="91"/>
<pinref part="R2" gate="G$1" pin="2"/>
<pinref part="U1" gate="G$1" pin="P26"/>
</segment>
</net>
<net name="GPIO27" class="0">
<segment>
<wire x1="-40.64" y1="-12.7" x2="-27.94" y2="-12.7" width="0.1524" layer="91"/>
<wire x1="-27.94" y1="-12.7" x2="-27.94" y2="-2.54" width="0.1524" layer="91"/>
<wire x1="-27.94" y1="-2.54" x2="-20.32" y2="-2.54" width="0.1524" layer="91"/>
<pinref part="R1" gate="G$1" pin="2"/>
<pinref part="U1" gate="G$1" pin="P27"/>
</segment>
</net>
<net name="SENSE" class="0">
<segment>
<wire x1="-50.8" y1="-25.4" x2="-50.8" y2="-27.94" width="0.1524" layer="91"/>
<wire x1="-50.8" y1="-25.4" x2="-38.1" y2="-25.4" width="0.1524" layer="91"/>
<junction x="-50.8" y="-25.4"/>
<pinref part="D1" gate="G$1" pin="C"/>
<pinref part="R4" gate="G$1" pin="2"/>
<label x="-46.99" y="-24.638" size="1.778" layer="95"/>
</segment>
<segment>
<wire x1="-20.32" y1="17.78" x2="-33.02" y2="17.78" width="0.1524" layer="91"/>
<pinref part="U1" gate="G$1" pin="SVP"/>
<label x="-32.512" y="18.542" size="1.778" layer="95"/>
</segment>
</net>
<net name="SIG" class="0">
<segment>
<wire x1="-76.2" y1="-25.4" x2="-76.2" y2="-27.94" width="0.1524" layer="91"/>
<wire x1="-76.2" y1="-25.4" x2="-88.9" y2="-25.4" width="0.1524" layer="91"/>
<junction x="-76.2" y="-25.4"/>
<pinref part="Q1" gate="G$1" pin="E"/>
<pinref part="R5" gate="G$1" pin="2"/>
<label x="-88.392" y="-24.638" size="1.778" layer="95"/>
</segment>
<segment>
<wire x1="-20.32" y1="12.7" x2="-33.02" y2="12.7" width="0.1524" layer="91"/>
<pinref part="U1" gate="G$1" pin="P34"/>
<label x="-32.512" y="13.462" size="1.778" layer="95"/>
</segment>
</net>
<net name="DQ" class="0">
<segment>
<wire x1="45.72" y1="-7.62" x2="33.02" y2="-7.62" width="0.1524" layer="91"/>
<wire x1="33.02" y1="-7.62" x2="20.32" y2="-7.62" width="0.1524" layer="91"/>
<wire x1="33.02" y1="-5.08" x2="33.02" y2="-7.62" width="0.1524" layer="91"/>
<junction x="33.02" y="-7.62"/>
<pinref part="U2" gate="G$1" pin="DQ"/>
<pinref part="U1" gate="G$1" pin="P4"/>
<pinref part="R6" gate="G$1" pin="1"/>
<label x="24.13" y="-6.858" size="1.778" layer="95"/>
</segment>
</net>
<net name="+3V3" class="0">
<segment>
<wire x1="-20.32" y1="22.86" x2="-27.94" y2="22.86" width="0.1524" layer="91"/>
<pinref part="U1" gate="G$1" pin="3V3"/>
<pinref part="SUPV1" gate="G$1" pin="+3V3"/>
</segment>
<segment>
<wire x1="-76.2" y1="-15.24" x2="-76.2" y2="-12.7" width="0.1524" layer="91"/>
<pinref part="Q1" gate="G$1" pin="C"/>
<pinref part="SUPV2" gate="G$1" pin="+3V3"/>
</segment>
<segment>
<wire x1="45.72" y1="-5.08" x2="40.64" y2="-5.08" width="0.1524" layer="91"/>
<wire x1="40.64" y1="-5.08" x2="40.64" y2="2.54" width="0.1524" layer="91"/>
<pinref part="U2" gate="G$1" pin="VDD"/>
<pinref part="SUPV3" gate="G$1" pin="+3V3"/>
</segment>
<segment>
<wire x1="33.02" y1="5.08" x2="33.02" y2="7.62" width="0.1524" layer="91"/>
<pinref part="R6" gate="G$1" pin="2"/>
<pinref part="SUPV4" gate="G$1" pin="+3V3"/>
</segment>
</net>
<net name="GND" class="0">
<segment>
<wire x1="-20.32" y1="-10.16" x2="-25.4" y2="-10.16" width="0.1524" layer="91"/>
<pinref part="U1" gate="G$1" pin="GND1"/>
<pinref part="SUPG1" gate="G$1" pin="GND"/>
</segment>
<segment>
<wire x1="-50.8" y1="-38.1" x2="-50.8" y2="-40.64" width="0.1524" layer="91"/>
<pinref part="R4" gate="G$1" pin="1"/>
<pinref part="SUPG2" gate="G$1" pin="GND"/>
</segment>
<segment>
<wire x1="-76.2" y1="-38.1" x2="-76.2" y2="-40.64" width="0.1524" layer="91"/>
<pinref part="R5" gate="G$1" pin="1"/>
<pinref part="SUPG3" gate="G$1" pin="GND"/>
</segment>
<segment>
<wire x1="45.72" y1="-10.16" x2="40.64" y2="-10.16" width="0.1524" layer="91"/>
<wire x1="40.64" y1="-10.16" x2="40.64" y2="-15.24" width="0.1524" layer="91"/>
<pinref part="U2" gate="G$1" pin="GND"/>
<pinref part="SUPG4" gate="G$1" pin="GND"/>
</segment>
</net>
</nets>
</sheet>
</sheets>
</schematic>
</drawing>
</eagle>
