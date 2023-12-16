#!/usr/bin/python3
import RPi.GPIO as GPIO                # GPIO 핀으로 부터 불꽃 감지 센서의 값을 읽기 위함
from datetime import datetime          # 일정 시간 경과했는지 계산하기 위함
import time                            # 일정 시간 대기를 위한 sleep() 함수 사용을 위함
import subprocess                      # Shell 명령 수행 목적, Shell 명령을 통한 DB Query 실행

#GPIO SETUP
channel = 17                 # 불꽃 감지 센서 연결한 핀 번호 설정
GPIO.setmode(GPIO.BCM)       # GPIO 핀에 대한 사용 시스템을 BCM 지정 방식 사용
GPIO.setup(channel, GPIO.IN) # 불꽃 감지 센서가 연결된 핀을 입력 모드로 설정
                             # 불꽃 감지 센서가 보내온 신호를 읽어 오기 위함

phones = [] # 수신받을 휴대폰 번호들을 등록할 List 초기화 ( 수신자 전화번호 List )
phones.append( "010-0000-0000" )  #팀장
phones.append( "010-1234-5678" )  #과장
phones.append( "010-1111-2222" )  #계장
phones.append( "010-2222-3333" )  #주임
phones.append( "010-3333-4444" )  #시설 팀장

call_no = "012-345-6789" #회신 전화 번호( 발신자 전화번호 )

msg_t1 = "화재 감지 긴급재난 문자"                         #화재 발생시 사용할 메시지 제목
msg1 = "서버실 화재 감지!!!\n신속한 화재 진압 바랍니다."   #화재 발생시 사용할 메시지 내용

msg_t2 = "화재 상황 해제 안내"                             #화재 진압되었을때 사용할 메시지 제목
msg2 = "서버실 화재 상황 해제되었습니다."                  #화재 진압되었을때 사용할 메시지 내용

interrupt_time = 0     # 이전 불꽃 감지한 마지막 시간값 초기화
is_fire = False        # 화재 감지 상황을 체크하기 위한 변수 
                       # 초기화 시킴, ( True : 화재 상황, False : 일상 상황 )

act_interval = []              # 화재 발생시 전송되는 메시지 간의 시간 간격 설정 List
                               # 유튜브에 올린 시험 동영상에서는 시간 간격을 2~5초 이내로 짧게 설정함
act_interval.append( 10 )      # 최초 메시지 발송후 다음 메시지 재발송까지 대기 시간(초) 설정 
                               # ( 재난 1차 메시지와  2차 메시지 사이의 시간 간격 )
act_interval.append( 1 * 60 )  # 재난 2차 메시지와 3차 메시지 사이의 시간 간격 설정
act_interval.append( 5 * 60 )  # 재난 3차 메시지와 4차 메시지 사이의 시간 간격 설정
act_interval.append( 10 * 60 ) # 재난 4차 메시지와 5차 메시지 사이의 시간 간격 설정
act_interval.append( 30 * 60 ) # 재난 5차 메시지와 6차 메시지 사이의 시간 간격 설정
                               # 마지막 등록한 시간 간격으로 화재가 진압될때까지 메시지 반복 전송함

sms_i = 0          # 재난 안내 문자 발송 횟수 count 변수 초기화
sms_time = 0       # 메시지 전송한 시간
c_interval = 0     # 다음 문자 발송시까지 기다리는 시간 간격 값 ( 초 )
                   # 최초 재난 안내 문자는 상황 발생, 즉시( 0 ) 전송함

o_id = 'oraID'               #Oracle DBMS 계정 ID
o_pass = 'oraPASS'           #Oracle DBMS 계정 password
o_ip = '192.168.0.7'         #Oracle DBMS 서버 주소
o_port = '1521'              #Oracle DBMS 서비스 포트
o_sid = 'oraSID'             #Oracle DBMS SID

qry_file = "/run/user/1000/sendsms.sql" #실행할 쿼리를 저장할 경로 및 파일명 
                                        # 메모리를 마운트한 휘발성 디렉터리 영역에 저장
                                        # ( SD카드 볼륨에 비해 처리 속도 향상 효과 등 )
sqlcl="/opt/oracle/sqlcl/bin/sql -s "  # sql 실행기 sqlcl 경로 지정
                                       # 불필요한 메시지들이 화면에 표시되지 않게 -s 옵션 추가
o_con= sqlcl + " " + o_id + "/" + o_pass + "@" + o_ip + ":" + o_port + ":" + o_sid   
                                       # Oracle 접속 및 쿼리 실행을 위한 명령 생성
exec_qry = o_con + " @" + qry_file     # Oracle 쿼리 실행 명령 
                                       # sql 실행기가 sql script file을 읽어 와서 쿼리 실행하게 함
#exec_qry += " & "      #  background 실행한다면...

qry_head = "set heading off"    # 쿼리 파일에 기록할 쿼리 실행전 처리할 설정등의 기타 명령 등록 
                                # set heading off : 쿼리 결과 head에 해당하는 필드명 표시하지 않음
                                # ( insert에서는 의미 없으나 실행에 영향없음 )
#qry_head += "\n" + "set colsep ',' "   #필드간 구분자를 comma 사용 ( select 문에서 의미 있음 )
qry = ""                                #실행할 쿼리 초기화
qry_tail = "\n" + "quit"                #실행할 쿼리 뒷부분에 추가 실행해야할 명령 ( 종료 명령 등 )

def sms_qry( msg_tit, msg, phone ):   # sms 발송할 개별 Query 생성 함수
  ### msg_tit : 메시지 제목
  ### msg     : 메시지 내용
  ### phone   # 수신자 전화번호
  ### 
  qry = "insert into sdk_sms_send ( msg_id, user_id, schedule_type, subject, sms_msg, callback_url, now_date, send_date, callback, dest_info) "
  qry += " values ( sdk_sms_seq.nextval, 'testid',0, '" + msg_tit + "', '" + msg + "', '',"
  qry += " to_char(sysdate,'yyyymmddhh24miss'), to_char(sysdate,'yyyymmddhh24miss'), '" + call_no + "', '^" + phone + "' ); "
  #
  return qry
  #
#

def send_sms( flag ) : # 발송할 Query file 생성 및 문자 메시지 발송을 위한 함수
  qry = ""
  if flag == "화재" :    #화재 상황일 경우
    msg_t = msg_t1       #화재 상황을 알리는 메시지 제목과
    msg = msg1           #전송할 메시지를 설정함
  elif flag == "해제" :  #화재가 진압된 상황일 경우에는
    msg_t = msg_t2       #화재가 진압되었음을 알리는 메시지 제목과
    msg = msg2           #안내될 메시지를 설정함
  else :
    msg_t = ""
    msg = ""
  #
  for phone in phones :                        #수신자 List에 등록된 모든 휴대폰 번호별 발송 쿼리 생성함
    qry += sms_qry( msg_t, msg, phone ) + "\n" 
  #
  qry_content = qry_head + "\n" + qry + qry_tail # 쿼리 파일에 저장할 내용 생성 
                                           # ( file Head + 수신자별 SMS 발송용 insert query + file Tail ) 
  #
  f = open( qry_file, "w" )                #쿼리를 저장할 파일 open ( overwrite 기록 모드 )
  f.write( qry_content )                   #SQL 파일에 실행할 쿼리 내용 저장
  f.close()                                #쿼리 파일 close
  #
  ####### 아래 내용은 발송 현황을 화면에 표시하기 위한 목적으로 추가함
  result = subprocess.getoutput( exec_qry ) #휴대폰 문자 메시지 발송 처리
  print( "===============" )
  #print( result )
  print( flag, "메시지 전송 순번:",sms_i, " 다음 메시지 전송 시간 간격:", c_interval, " 전송시간:",sms_time )
  #print( qry_content )
  print( "===============" )
  #print( "\n\n\n" )
#

def is_stat( ck_flag, cnt = 5 ): #flag로 지정한 상태가 cnt 횟수 동안 계속 유지 되고 있는지 반복 확인 함수
                                 #불꽃이 계속 유지 중인 상태에서 불꽃 꺼짐 인터럽트가 발생됨
                                 #화재가 진압되지 않았는데도 잘못된 메시지가 발송되지 않게하기 위한 목적
  r = True  # return 값
  i = 0     # 점검 횟수 count
  for i in range( 0, cnt ) :
    pin = GPIO.input( channel ) 
    if pin == ck_flag :  # 불꽃 감지 센서로 부터 읽은 값이 지정한 횟수 동안 계속 유지해야
      pass               # 해당 상태가 유지되고 있다는 결과를 돌려 주게됨
    else :               # 한번이라도 지정한 상태값이 아니라면
      r = False          # 확인 요청한 상황이 아니라는 결과를 돌려주게됨
      break 
    #
    #time.sleep( 100/1000 )    # 100ms 대기후 재점검
  #
  return r
##

def not_fire():  # 불꽃이 사라졌을때 처리하는 함수
  global sms_time, c_interval, sms_i # SMS 발송을 컨트롤하기 위한 전역 변수 
  if c_interval != 0 :
    send_sms( "해제" ) # 불이 꺼졌음을 안내하는 문자 메시지 전송함 
    c_interval = 0     #현 상황 해제와 동시에 다음 상황 발생시 메시지가 즉각적으로 전송될 수 있게 설정
    sms_i = 0          #재난 상황 안내 메시지 전송된 횟수를 초기화 시킴
  #
#
 
def fire():   # 불꽃 감지되었을 경우 실행 함수
  global interrupt_time              # 불꽃 감지 Interrupt 발생한 시간 저장 변수
  global sms_time, c_interval, sms_i # SMS 발송을 컨트롤하기 위한 전역 변수
  #
  interrupt_time = datetime.today()   #인터럽트 걸린 시간 기록용  전역 변수를 갱신함 
  if sms_i == 0 :                     # 불꽃 감지 후 첫번째 발송하는 메시지일 경우 즉시 전송함
    send_sms( "화재" )
    c_interval = act_interval[ 0 ]    # 첫번째 메시지간 시간 간격 값을 다음 간격값으로 설정
    sms_i += 1                        #sms 발송 count를 1 증가 시킴
    sms_time = datetime.today()       #sms 발송한 시간을 갱신함
  elif sms_i > 0 :                   # 불꽃 감지하여 메시지를 한번이라도 보낸 이후라면
    if ( datetime.today() - sms_time ).seconds > c_interval : # 메시지간 대기 시간 경과했을 경우 재발송
      send_sms( "화재" )                                      # 메시지 발송
      if sms_i >= len( act_interval ) :                       # 등록된 메시지간 대기 시간 이후 전송은
        c_interval = act_interval[ len( act_interval ) - 1 ]  # 등록된 마지막 메시지간 대기 시간으로 설정
      else :                                                  # 메시지간 대기 시간 등록된 전송 횟수일경우
        c_interval = act_interval[ sms_i ]                    # 메시지간 대기 시간을 등록된 List의 값으로
      #
      sms_i += 1                   #sms 발송 count를 1 증가 시킴
      sms_time = datetime.today()  #sms 발송한 시간을 갱신함
      #
    #
  #
#

def h_event( channel ):  # 불꽃 감지 센서의 상태 변경이 발행했을 경우 인터럽트에 의해 처리하는 함수
  global is_fire
  pin = GPIO.input( channel ) # 불꽃 감지 센서가 연결된 Pin 상태 확인 - 1: 불꽃 감지, 0: 불꽃 사라짐 감지
  if pin :                    # 불꽃 발생 인터럽트가 수신되었을 경우
    if is_fire :              # 화재 상황을 이미 처리하고 있는 상태였다면
      pass                    # 처리없이 통과함
    else :                   # 화재 상황이 아닌 상태에서 불꽃 감지을 했다면
      fire()                 # 화재에 대한 처리 후
      is_fire = True         # 화재 감지 상태 표시함
    #
  else :                     #불꽃 사라짐 인터럽트 수신일 경우 
    if is_fire :             #화재 상황 처리 중이었을 경우라면
      if is_stat( 0, 30 ) :  # 불꽃이 사라진 상태가 확실한지 여러번 반복 확인 후
                             # 불꽃이 확실히 사라진 상태인 것이 확인되었을 경우에
        if is_fire :         # 화재 상황을 처리 중이었을 경우라면
          not_fire()         # 화재 종료에 대한 안내 처리
          is_fire = False    # 화재 상황이 아님을 표시
        #
      else :      # 화재 상황에서 불꽃 꺼짐 인터럽트 수신하였으나 재확인 결과 불꽃 남아 있음
        pass      # 특별한 조치없이 화재 상황 지속함 ( 계속 화재 중임에도, 화재 종료 안내 알림되지 않게 )
      #
    else :        # 화재 상황이 아닌데 볼꽃 사라짐 인트럽트를 수신했을 경우
      pass        # 특별한 조치를 취하지 않음
    #
  #
#

def check_stat() :   # Polling 방식으로 추가 불꽃 상태 감지 및 인터럽트 없이도 메시지 반복 발송될 수 있게
  global is_fire
  if is_fire :               # 화재 상황이 계속되고 있을 경우라면
    if is_stat( False, 20 ) :# 화재 진압되었음에도 인터럽트가 감지하지 못했을 경우에 대비해 상태 점검함
      not_fire()             # 화재 종료 상태 점검하여 화재 종료가 확인된다면 화재 종료 메시지 보냄
      is_fire = False
    else :                 # 여전히 불꽃이 감지되고 있을 경우라면
      fire()               # 화재 상황 처리함 ( 일정 시간 경과 후에 상황 안내 문자 발생될 수 있게 해줌 )
    #
  else :                   # 화재가 발생하지 않은 일상 상황에서의 처리
    if is_stat( True ) :   # 불꽃이 감지 점검하여, 불꽃을 감지하였다면 ( 인터럽트 오류로 처리 못한 상황 )
      fire()                #화재 상황 처리함 
      is_fire = True
    else : # 
      pass
    #
  #
#
GPIO.add_event_detect( channel, GPIO.BOTH, callback=h_event, bouncetime=300 ) # Interrupt 방식 불꽃 감지
 
# infinite loop
while True:       #화재 감지 interrupt가 계속 실행될 수 있게 무한 대기하면서 인터럽트 발생 상황 check함
  check_stat()    # Polling 방식의 화재 상황 정기 점검
  time.sleep( 300/1000 )                 # 300ms 대기 후 무한 반복 처리함
#