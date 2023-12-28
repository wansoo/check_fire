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
phones.append( "010-0000-1111" )  #팀장
phones.append( "010-1234-5678" )  #과장
phones.append( "010-1111-2222" )  #계장
phones.append( "010-2222-3333" )  #주임
phones.append( "010-3333-4444" )  #시설 팀장

call_no = "012-1234-5678" #회신 전화 번호( 발신자 전화번호 )

msg_t1 = "화재 감지 긴급재난 문자"                  #화재 발생시 사용할 메시지 제목
msg1 = "서버실 화재 감지!!!\n신속한 화재 진압 바랍니다."   #화재 발생시 사용할 메시지 내용

msg_t2 = "화재 상황 해제 안내"                        #화재 진압되었을때 사용할 메시지 제목
msg2 = "서버실 화재 상황 해제되었습니다."                  #화재 진압되었을때 사용할 메시지 내용

interrupt_time = 0          # 이전 불꽃 감지한 마지막 시간값 초기화
chk_time = datetime.today() # 현재 시간으로 초기화 시킴
is_fire = False             # 화재 감지 상황을 체크하기 위한 변수 
                            #   - 초기화 시킴, ( True : 화재 상황, False : 일상 상황 )
ck_lock = False             # 이전 시도 SMS 발송이 처리가 끝날때까지 재 발송 시도되지 않게 처리(동시 실행 제어)
                            # 인터럽트 방식과 Polling 방식의 동시 실행으로 인한 문제 해결 방안

act_interval = []                # 화재 발생시 전송되는 메시지 간의 시간 간격 설정 List
act_interval.append( 10 )        # 최초 메시지 발송후 다음 메시지 재발송까지 대기 시간(초) 설정 
                                 # ( 재난 1차 메시지와  2차 메시지 사이의 시간 간격 )
act_interval.append( 1 * 60 )    # 재난 2차 메시지와 3차 메시지 사이의 시간 간격 설정 ( 1분 )
act_interval.append( 5 * 60 )    # 재난 3차 메시지와 4차 메시지 사이의 시간 간격 설정 ( 5분 )
act_interval.append( 10 * 60 )   # 재난 4차 메시지와 5차 메시지 사이의 시간 간격 설정 ( 10분 )
act_interval.append( 30 * 60 )   # 재난 5차 메시지와 6차 메시지 사이의 시간 간격 설정, 마지막 등록한 시간 간격으로 화재가 진압될때까지 메시지 반복 전송함

sms_i = 0          # 재난 안내 문자 발송 횟수 count 변수 초기화
sms_time = 0       # 메시지 전송한 시간
c_interval = 0     # 다음 문자 발송시까지 기다리는 시간 간격 값 ( 초 ), 최초 재난 안내 문자는 상황 발생시  대기하지 않고 즉시( 0 ) 발송함

qry_file = "/run/user/1000/sendsms.sql" #실행할 쿼리를 저장할 파일명 
                                        #( 메모리를 마운트한 휘발성 디렉터리 영역에 저장, 
                                        #     SD카드 볼륨에 비해 처리 속도 향상 등의 효과 )
sqlcl="/opt/oracle/sqlcl/bin/sql -s "   #sql 실행기 sqlcl 경로 지정, 
                                        #  쿼리 실행 중 발생하는 불필요한 메시지 표시되지 않게 -s 옵션 추가

o_id = 'oraID'               #Oracle DBMS 계정 ID
o_pass = 'oraPASS'           #Oracle DBMS 계정 password
o_ip = '192.168.0.7'         #Oracle DBMS 서버 주소
o_port = '1521'              #Oracle DBMS 서비스 포트
o_sid = 'oraSID'             #Oracle DBMS SID

o_con= sqlcl + " " + o_id + "/" + o_pass + "@" + o_ip + ":" + o_port + ":" + o_sid   
                                                  # Oracle 접속 및 쿼리 실행 명령 생성
exec_qry = o_con + " @" + qry_file                # Oracle 쿼리 실행 명령
                                                  # sql 실행기가 sql script file을 읽어 와서 쿼리 실행하게 함
#exec_qry += " & "   #  background 실행한다면...

qry_head = "set heading off"    # 쿼리 파일에 기록할 쿼리 실행전 처리할 설정등의 기타 명령 등록 
                                # set heading off : 쿼리 결과 head에 해당하는 필드명 표시하지 않음
                                # ( insert에서는 의미 없음, 실행에 영향없음 )
#qry_head += "\n" + "set colsep ',' " #필드간 구분자를 comma 사용 ( select 문에서 의미 있음 )
qry = ""                              #실행할 쿼리 초기화
qry_tail = "\n" + "quit"              #실행할 쿼리 뒷부분에 추가 실행해야할 명령 ( 종료 명령 등 )


def sms_qry( msg_tit, msg, phone ):   # sms 발송할 개별 Query 생성 함수
  ### msg_tit : 메시지 제목
  ### msg     : 메시지 내용
  ### phone   # 수신자 전화번호
  ### 
  qry = "insert into sdk_sms_send ( msg_id, user_id, schedule_type, subject, sms_msg, callback_url, now_date, send_date, callback, dest_info) "
  qry += " values ( sdk_sms_seq.nextval, 'testid',0, '" + msg_tit + "', '" + msg + "', '',"
  qry += " to_char(sysdate,'yyyymmddhh24miss'), to_char(sysdate,'yyyymmddhh24miss'), '" + call_no + "', '^" + phone + "' ); "
  #
  #qry = "select * from dual; "
  #
  return qry
  #
#

def send_sms( flag ) : # 발송할 Query file 생성 및 문자 메시지 발송 함수
  global ck_lock   # 동시 실행되지 못하게 lock을 걸기 위한 전역 변수
  global chk_time  # 메시지 발송 시간 비교 확인용 변수 
  global is_fire, sms_i, c_interval
  #
  while ck_lock :     # Lock이 걸린 상태라면 Lock이 풀릴때까지 대기함
    time.sleep(5/1000)# 5ms 대기후 반복
  #
  ck_lock = True  # Lock을 걸어 다른 Thread가 동시 실행되지 못하게 차단함
  #
  qry = ""
  if flag == "화재" :    #화재 상황일 경우
    msg_t = msg_t1       #화재 상황을 알리는 메시지 제목과
    msg = msg1           #메시지를 설정함
  elif flag == "해제" :  #화재가 진압된 상황일 경우에는
    msg_t = msg_t2       #화재가 진압되었음을 알리는 메시지 제목과
    msg = msg2           #안내 메시지를 설정함
  else :
    msg_t = ""
    msg = ""
  #
  #
  s = ( interrupt_time - chk_time ).seconds # 이전 메시지 발송한 시간 후 시간(초)이 얼마나 경과했는지 계산
  if s <= act_interval[0]  : # Polling 방식과, Interrupt 방식 2중 동시 실행 감지로 동일 메시지 반복 전송 차단 목적
                             # 이전 메시지 발송 후 첫번째 등록된 시간 간격 이내에 메시지가 반복 발송되지 않게 차단 설정함
    pass
  else :
    for phone in phones :                         #수신자 List에 등록된 모든 휴대폰 번호별 발송 쿼리 생성함
      qry += sms_qry( msg_t, msg, phone ) + "\n" 
    #
    qry_content = qry_head + "\n" + qry + qry_tail  # 쿼리 파일에 저장할 내용 생성 
                                                    #( file Head + 수신자별 SMS 발송용 insert query + file Tail ) 
    #
    f = open( qry_file, "w" )                    #쿼리를 저장할 파일 open
    f.write( qry_content )                       #SQL 파일에 실행할 쿼리 내용 저장
    f.close()                                    #쿼리 파일 close
    #
    result = subprocess.getoutput( exec_qry )    #휴대폰 문자 메시지 발송 처리 ( DB Insert 실행 )
    print( "===============" )
    #print( result )
    print( flag, "메시지 전송 순번:",sms_i, " 다음 메시지 전송 시간 간격:", c_interval, " 전송시간:",sms_time )
    #print( qry_content )
    print( "===============" )
    print( "\n\n\n" )
    chk_time = interrupt_time    # 다음 메시지 발송시 비교 검토를 위해 현 처리 시간 기록 남김
    #
    if flag == "화재" : #화재 안내 메시지를 전송했을 경우에는
      is_fire = True  #화재 상태로 전환함
      sms_i += 1      #SMS 문자 보낸 전송 횟수 count
    elif flag == "해제" : # 화재 해제 메시지를 전송했을 경우에는 
      is_fire = False   # 화재 해제 상태로 전환함
      sms_i = 0         # 재난 상태 메시지 전송 횟수 초기화함
      c_interval = 0    # 메시지 재 전송 시간 간격 값 0으로 초기화하여 다음 재난시 메시지 즉시 발송되게 처리
    #
  #
  ck_lock = False    # Lock을 해제하여 다른 Thread가 실행될 수 있게 처리함
#

def is_stat( ck_flag, cnt = 5 ) :#flag로 지정한 상태가 cnt 횟수 동안 계속 유지 되고 있는지 반복 확인 함수
                                 #불꽃이 계속 유지 중인 상태에서 불꽃 꺼짐 인터럽트가 발생됨
                                 #화재가 진압되지 않았는데도 잘못된 메시지가 발송되지 않게하기 위한 목적
  r = True     # return 값
  i = 0        # 점검 횟수 count 초기화
  for i in range( 0, cnt ) :   # 지정한 횟수 만큼 반복하면서 지정한 상태가 계속 유지되고 있는 지 점검함
    pin = GPIO.input( channel )# 센서의 출력 상태값 읽어옴
    if pin == ck_flag :  # 불꽃 감지 센서로 부터 읽은 값이 지정한 횟수 동안 계속 유지해야
      pass               # 해당 상태가 유지되고 있다는 결과를 돌려 주게됨
    else :               # 한번이라도 지정한 상태값이 아니라면
      r = False          # 확인 요청한 상태를 유지하지 않고 있다는 결과를 돌려주게됨
      break 
    #
    time.sleep( 50/1000 )    # 50ms 대기후 재점검
  #
  return r
##

def not_fire():  # 불꽃이 사라졌을때 처리하는 함수
  if c_interval != 0 :
    send_sms( "해제" ) # 불이 꺼졌음을 안내하는 문자 메시지 전송함 
  #
#
 
def fire():   # 불꽃 감지되었을 경우 실행 함수
  global interrupt_time              # 불꽃 감지 Interrupt 시간 
  global sms_time, c_interval # SMS 발송을 컨트롤하기 위한 전역 변수
  #
  interrupt_time = datetime.today()   #인터럽트 걸린 현 시간 저장용  전역 변수를 갱신함 
  if sms_i == 0 :                     # 불꽃 감지 후 첫번째 발송하는 메시지일 경우 즉시 전송함
    c_interval = act_interval[ sms_i ]# 첫번째 메시지간 시간 간격 값을 다음 간격값으로 설정
    send_sms( "화재" )                  # 화재가 발생했음을 안내함( 메시지 전송 )
    sms_time = datetime.today()       #sms 발송한 시간을 갱신함
  #
  elif sms_i > 0 : # 불꽃 감지하여 메시지를 한번이라도 보낸 이후라면 
    if ( datetime.today() - sms_time ).seconds > c_interval : #이전 메시지 발송 시도 후 지정한 시간이 지났을 경우에 메시지를 다시 전송 처리함
      if sms_i >= len( act_interval ) :                       #메시지 전송한 횟수가 메시지간 재전송 설정 시간 갯수보다 더 많다면
        c_interval = act_interval[ len( act_interval ) - 1 ]  #메시지 재 전송 간격 값을 등록된 마지막 값으로 설정함
      else :                                                  #메시지 재 전송 간격이 등록되어 있는 전송횟수라면
        c_interval = act_interval[ sms_i ]                    #해당 전송 횟수에 매칭하는 재 전송 시간 간격값 설정함
      #
      send_sms( "화재" )            # 화재 상태를 안내하는 메시지 발송
      sms_time = datetime.today() #sms 발송한 시간을 갱신함
    #
  #
#


def h_event( channel ):  #불꽃 감지 센서로부터 이벤트 받아 처리하는 함수
  pin = GPIO.input( channel )  # 불꽃 감지 센서가 연결된 Pin 상태 확인 - 1: 불꽃 감지, 0: 불꽃 사라짐 감지
  if pin :   # 불꽃 발생 인터럽트 수신일 경우
    if is_fire :   #이미 화재 상태를 처리 하고 있는 상황라면
      pass         #아무 처리도 하지 않음
    else :         #평시 상황에서 화재를 처음 감지한 상황이라면
      fire()       #화재에 대한 처리
    #
  else :           #불꽃 사라짐 인터럽트 수신일 경우 
    if is_fire :   #화재 상황 처리 중이었을 경우라면
      if is_stat( 0, 30 ) :  # 일시적으로 불꽃 감지를 못한 상황인지, 화재 상황이 완전히 종료된 것인지 확인하여
                             # 화재 상황이 완전히 종료되었음이 확인
        if is_fire :         # 화재 상황을 처리
          not_fire()                #화재 종료에 대한 처리
        #
      else :                 # 화재 상황에서 불꽃 꺼짐인터럽트 수신하였으나 재 확인 결과 불꽃 남아 있음
        pass                 # 특별한 조치없이 화재 상황 지속함
      #
    else :         # 화재 상황이 아닌데 볼꽃 사라짐 인트럽트를 수신했을 경우
      pass         # 특별한 조치를 취하지 않음
    #
  #
#


def check_stat() :   # Polling 방식으로 추가 불꽃 상태 감지 및 적절한 시점에 반복 메시지 발송 처리  
  if is_fire :                  # 화재가 발생한 상황에서의 처리 
    if is_stat( False, 20 ) :   # 화재가 완전히 전압되었는지 여부를 체크함, 좀더 엄격한 확인이 필요함, 불꽃이 감지되지 않는다면
      not_fire()     # 화재 진압 상황 처리함 
      #
    else :          # 여전히 불꽃이 감지되고 있을 경우라면
      fire()        # 화재 상황 처리함 
    #
  else :            # 화재가 발생하지 않은 일상 상황에서의 처리
    if is_stat( True ) :   # 불꽃이 감지되는지 점검하여, 불꽃을 감지하였다면
      fire()               #화재 상황 처리함 
    else : # 
      pass
    #
  #
#

GPIO.add_event_detect( channel, GPIO.BOTH, callback=h_event, bouncetime=200 )  # Interrupt 방식의 불꽃 감지 처리
 
# infinite loop
while True:       #화재 감지 interrupt가 계속 실행될 수 있게 무한 대기하면서 인터럽트 발생 상황 check함
  check_stat()    # Polling 방식으로 화재 상황 추가 점검함
  #
  time.sleep( 500/1000 )                 # 300ms 대기 후 반복 처러함
#
